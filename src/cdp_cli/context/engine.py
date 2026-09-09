"""Assemble a ContextBundle from current operational state.

Calls existing business tools. Does not generate SQL from the question
and does not embed warehouse rows.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import duckdb

from .. import metrics as M
from ..business import (
    action_for_reason,
    get_business_snapshot,
    get_channel_as_of,
    get_ingest_health,
    get_inventory_attention_queue,
    get_item,
    get_item_history,
)
from .intents import ITEM_SCOPED, REQUIRED_CONCEPTS, extract_sku, resolve_intent
from .model import (
    ContextBundle,
    ContextEvent,
    ContextLink,
    ContextObject,
    MissingContext,
)


def _utcnow() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(
        timespec="seconds"
    ) + "Z"


def _missing(concept: str, reason: str, intent: str) -> MissingContext:
    return MissingContext(concept=concept, reason=reason, required_for=intent)


def _object(type_: str, id_: str, properties: dict[str, Any]) -> ContextObject:
    return ContextObject(type=type_, id=str(id_), properties=properties)


def _link(type_: str, src: ContextObject, dst: ContextObject) -> ContextLink:
    return ContextLink(type=type_, from_ref=src.ref(), to_ref=dst.ref())


def _repricing_rules(
    listing: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    age = None if listing is None else listing.get("listing_age_days")
    watch_rate = None if listing is None else listing.get("watch_rate")
    offers = 0 if listing is None else listing.get("offers") or 0
    stale = age is not None and age >= M.STALE_LISTING_DAYS
    high_no_offer = (
        watch_rate is not None
        and watch_rate >= M.HIGH_WATCH_RATE
        and offers == 0
    )
    return [
        {
            "name": "stale_listing",
            "kind": "rule",
            "threshold_days": M.STALE_LISTING_DAYS,
            "applies": stale,
            "definition": M.METRICS["stale_listing"].definition,
        },
        {
            "name": "high_attention_no_offers",
            "kind": "heuristic",
            "threshold_watch_rate": M.HIGH_WATCH_RATE,
            "applies": high_no_offer,
            "definition": (
                f"Active listing with watch_rate >= {M.HIGH_WATCH_RATE} "
                "and zero offers — interest without conversion."
            ),
        },
    ]


def _assemble_item_graph(
    con: duckdb.DuckDBPyConnection,
    sku: str,
    *,
    need_history: bool,
) -> dict[str, Any]:
    item_payload = get_item(con, sku)
    item_data = item_payload.data["item"]
    listings = item_payload.data["listings"]
    orders = item_payload.data["orders"]
    item_obj = _object(
        "Item",
        item_data["sku"],
        {
            "sku": item_data["sku"],
            "product": item_data.get("product"),
            "status": item_data.get("status"),
            "condition": item_data.get("condition"),
            "acquisition_cost_cny": item_data.get("acquisition_cost_cny"),
            "target_price_usd": item_data.get("target_price_usd"),
            "acquired_at": item_data.get("acquired_at"),
            "inventory_age_days": item_data.get("inventory_age_days"),
        },
    )
    objects: list[ContextObject] = [item_obj]
    links: list[ContextLink] = []
    source_tools = ["get_item"]
    source_relations = list(item_payload.provenance.source_relations)

    listing_objs: list[ContextObject] = []
    for listing in listings:
        listing_obj = _object(
            "Listing",
            listing["listing_id"],
            {
                "listing_id": listing["listing_id"],
                "status": listing.get("status"),
                "price_usd": listing.get("price_usd"),
                "listed_at": listing.get("listed_at"),
                "sold_at": listing.get("sold_at"),
                "platform": listing.get("platform"),
                "listing_age_days": listing.get("listing_age_days"),
                "views": listing.get("views"),
                "watchers": listing.get("watchers"),
                "offers": listing.get("offers"),
                "watch_rate": listing.get("watch_rate"),
            },
        )
        objects.append(listing_obj)
        listing_objs.append(listing_obj)
        links.append(_link("HAS_LISTING", item_obj, listing_obj))
        platform = listing.get("platform")
        if platform:
            try:
                ch = get_channel_as_of(con, platform)
                source_tools.append("get_channel_as_of")
                version = (ch.data.get("versions") or [None])[0]
                props = {"platform": platform, "covered": ch.data.get("covered")}
                if version:
                    props.update(
                        {
                            "handle": version.get("handle"),
                            "standing": version.get("standing"),
                            "fee_pct": version.get("fee_pct"),
                            "channel_key": version.get("channel_key"),
                        }
                    )
                channel_obj = _object("Channel", platform, props)
                if all(o.ref() != channel_obj.ref() for o in objects):
                    objects.append(channel_obj)
                links.append(_link("ON_CHANNEL", listing_obj, channel_obj))
            except KeyError:
                pass

    history = None
    events: list[ContextEvent] = []
    engagement_rows: list[dict[str, Any]] = []
    if need_history:
        history = get_item_history(con, sku)
        source_tools.append("get_item_history")
        source_relations = list(
            dict.fromkeys(source_relations + history.provenance.source_relations)
        )
        engagement_rows = list(history.data.get("engagement") or [])
        for row in history.data.get("timeline") or []:
            events.append(
                ContextEvent(
                    type=row.get("type") or "event",
                    at=row.get("at"),
                    object_ref=item_obj.ref(),
                    source=row.get("source") or "",
                    detail=row.get("detail"),
                )
            )

    engagement_by_listing: dict[str, list[dict[str, Any]]] = {}
    for snap in engagement_rows:
        engagement_by_listing.setdefault(snap["listing_id"], []).append(snap)

    for listing_obj in listing_objs:
        snaps = engagement_by_listing.get(listing_obj.id, [])
        if not snaps:
            continue
        rollup = _object(
            "EngagementObservation",
            f"{listing_obj.id}:rollup",
            {
                "listing_id": listing_obj.id,
                "snapshot_count": len(snaps),
                "views": listing_obj.properties.get("views"),
                "watchers": listing_obj.properties.get("watchers"),
                "offers": listing_obj.properties.get("offers"),
                "watch_rate": listing_obj.properties.get("watch_rate"),
                "first_snapshot_at": snaps[0].get("snapshot_at"),
                "last_snapshot_at": snaps[-1].get("snapshot_at"),
            },
        )
        objects.append(rollup)
        links.append(_link("HAS_ENGAGEMENT", listing_obj, rollup))

    for order in orders:
        order_id = order.get("order_id") or order.get("order_line_key")
        order_obj = _object(
            "Order",
            order_id,
            {
                "order_id": order.get("order_id"),
                "listing_id": order.get("listing_id"),
                "status": order.get("status"),
                "price_usd": order.get("price_usd"),
                "revenue_usd": order.get("revenue_usd"),
                "order_at": order.get("order_at"),
            },
        )
        objects.append(order_obj)
        links.append(_link("RESULTED_IN", item_obj, order_obj))

    return {
        "item": item_data,
        "item_obj": item_obj,
        "listings": listings,
        "orders": orders,
        "objects": objects,
        "links": links,
        "events": events,
        "engagement_rows": engagement_rows,
        "source_tools": list(dict.fromkeys(source_tools)),
        "source_relations": source_relations,
        "history": history,
    }


def _reprice(
    con: duckdb.DuckDBPyConnection, sku: str, intent: str
) -> dict[str, Any]:
    graph = _assemble_item_graph(con, sku, need_history=True)
    missing: list[MissingContext] = []
    item = graph["item"]
    listings = graph["listings"]
    active = [lst for lst in listings if lst.get("status") == "active"]
    chosen = active[0] if active else (listings[0] if listings else None)

    if item.get("acquisition_cost_cny") is None:
        missing.append(
            _missing("acquisition_cost", "item has no acquisition_cost_cny", intent)
        )
    if not listings:
        missing.append(
            _missing("listing", "item has no listings", intent)
        )
        missing.append(
            _missing("listing_age", "no listing to age", intent)
        )
        missing.append(
            _missing("asking_price", "no listing price", intent)
        )
        missing.append(
            _missing("engagement", "no listing to observe", intent)
        )
    else:
        if chosen is None or chosen.get("listing_age_days") is None:
            missing.append(
                _missing("listing_age", "listed_at is missing", intent)
            )
        if chosen is None or chosen.get("price_usd") is None:
            missing.append(
                _missing("asking_price", "listing has no price_usd", intent)
            )
        if not graph["engagement_rows"]:
            missing.append(
                _missing(
                    "engagement",
                    "no engagement snapshots for this item's listings",
                    intent,
                )
            )
    if not graph["events"]:
        missing.append(
            _missing("item_history", "no events on the item timeline", intent)
        )

    metrics: dict[str, Any] = {
        "inventory_age_days": item.get("inventory_age_days"),
        "acquisition_cost_cny": item.get("acquisition_cost_cny"),
    }
    if chosen:
        metrics["listing_age_days"] = chosen.get("listing_age_days")
        metrics["asking_price_usd"] = chosen.get("price_usd")
        metrics["watch_rate"] = chosen.get("watch_rate")
        metrics["views"] = chosen.get("views")
        metrics["watchers"] = chosen.get("watchers")
        metrics["offers"] = chosen.get("offers")

    rules = _repricing_rules(chosen)
    facts = {
        "sku": sku,
        "item_status": item.get("status"),
        "listing_count": len(listings),
        "has_active_listing": bool(active),
    }
    return {
        **graph,
        "missing": missing,
        "metrics": metrics,
        "rules": rules,
        "facts": facts,
    }


def _focus(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    snap = get_business_snapshot(con)
    queue = get_inventory_attention_queue(con)
    health = get_ingest_health(con)
    objects = [_object("IngestRun", "trust", {"ok": health.data.get("ok")})]
    links: list[ContextLink] = []
    for rec in queue.data.get("recommendations") or []:
        rec_obj = _object("Recommendation", rec["sku"], rec)
        item_obj = _object("Item", rec["sku"], {"sku": rec["sku"]})
        if all(o.ref() != item_obj.ref() for o in objects):
            objects.append(item_obj)
        objects.append(rec_obj)
        links.append(_link("TARGETS", rec_obj, item_obj))
    return {
        "objects": objects,
        "links": links,
        "events": [],
        "missing": [],
        "metrics": {
            "owned_unlisted": snap.data.get("owned_unlisted"),
            "capital_tied_up_cny": snap.data.get("capital_tied_up_cny"),
            "stale_active_listings": snap.data.get("stale_active_listings"),
            "warehouse_trust_ok": snap.data.get("warehouse_trust_ok"),
        },
        "rules": [
            {
                "name": "attention_ranking",
                "kind": "heuristic",
                "definition": (
                    "unlisted_owned then stale_listing then "
                    "high_attention_no_offers; see get_inventory_attention_queue"
                ),
            }
        ],
        "facts": {
            "snapshot": snap.data,
            "attention": {
                "queue": queue.data.get("queue"),
                "recommendations": queue.data.get("recommendations"),
            },
            "trust": health.data,
        },
        "source_tools": [
            "get_business_snapshot",
            "get_inventory_attention_queue",
            "get_ingest_health",
        ],
        "source_relations": list(
            dict.fromkeys(
                snap.provenance.source_relations
                + queue.provenance.source_relations
                + health.provenance.source_relations
            )
        ),
    }


def _explain_attention(
    con: duckdb.DuckDBPyConnection, sku: str, intent: str
) -> dict[str, Any]:
    graph = _assemble_item_graph(con, sku, need_history=True)
    queue = get_inventory_attention_queue(con)
    row = next(
        (r for r in queue.data.get("queue") or [] if r.get("sku") == sku),
        None,
    )
    rec = next(
        (
            r
            for r in queue.data.get("recommendations") or []
            if r.get("sku") == sku
        ),
        None,
    )
    missing: list[MissingContext] = []
    if row is None:
        missing.append(
            _missing(
                "attention_reason",
                "sku is not in the current attention queue",
                intent,
            )
        )
        reason = None
        action = None
    else:
        reason = row.get("attention_reason")
        action = action_for_reason(reason) if reason else None
        rec_obj = _object(
            "Recommendation",
            sku,
            {
                "sku": sku,
                "attention_reason": reason,
                "action": action,
                "why": None if rec is None else rec.get("why"),
            },
        )
        graph["objects"].append(rec_obj)
        graph["links"].append(_link("TARGETS", rec_obj, graph["item_obj"]))

    metrics: dict[str, Any] = {
        "inventory_age_days": graph["item"].get("inventory_age_days"),
        "acquisition_cost_cny": graph["item"].get("acquisition_cost_cny"),
    }
    listing = graph["listings"][0] if graph["listings"] else None
    if listing:
        metrics["listing_age_days"] = listing.get("listing_age_days")
        metrics["watch_rate"] = listing.get("watch_rate")
        metrics["offers"] = listing.get("offers")
    if listing is None and reason == "unlisted_owned":
        pass
    elif row and reason != "unlisted_owned" and listing is None:
        missing.append(_missing("supporting_metrics", "no listing metrics", intent))

    rules = _repricing_rules(listing)
    graph["source_tools"] = list(
        dict.fromkeys(graph["source_tools"] + ["get_inventory_attention_queue"])
    )
    return {
        **graph,
        "missing": missing,
        "metrics": metrics,
        "rules": rules,
        "facts": {
            "sku": sku,
            "in_queue": row is not None,
            "attention_reason": reason,
            "action": action,
        },
    }


def _item_state(con: duckdb.DuckDBPyConnection, sku: str) -> dict[str, Any]:
    graph = _assemble_item_graph(con, sku, need_history=False)
    listing = graph["listings"][0] if graph["listings"] else None
    metrics: dict[str, Any] = {
        "inventory_age_days": graph["item"].get("inventory_age_days"),
        "acquisition_cost_cny": graph["item"].get("acquisition_cost_cny"),
    }
    if listing:
        metrics["listing_age_days"] = listing.get("listing_age_days")
        metrics["watch_rate"] = listing.get("watch_rate")
    return {
        **graph,
        "missing": [],
        "metrics": metrics,
        "rules": [],
        "facts": {
            "sku": sku,
            "status": graph["item"].get("status"),
            "listing_count": len(graph["listings"]),
            "order_count": len(graph["orders"]),
        },
    }


def _item_history_intent(
    con: duckdb.DuckDBPyConnection, sku: str, intent: str
) -> dict[str, Any]:
    graph = _assemble_item_graph(con, sku, need_history=True)
    missing: list[MissingContext] = []
    if not graph["events"]:
        missing.append(_missing("events", "no timeline events", intent))
    return {
        **graph,
        "missing": missing,
        "metrics": {
            "inventory_age_days": graph["item"].get("inventory_age_days"),
        },
        "rules": [],
        "facts": {"sku": sku, "event_count": len(graph["events"])},
    }


def _recent_changes() -> dict[str, Any]:
    return {
        "objects": [],
        "links": [],
        "events": [],
        "missing": [
            _missing(
                "previous_snapshot",
                "no persisted prior business snapshot to diff against",
                "recent_changes",
            )
        ],
        "metrics": {},
        "rules": [],
        "facts": {},
        "source_tools": [],
        "source_relations": [],
    }


def _health(con: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    health = get_ingest_health(con)
    obj = _object("IngestRun", "trust", health.data)
    return {
        "objects": [obj],
        "links": [],
        "events": [],
        "missing": [],
        "metrics": {},
        "rules": [],
        "facts": health.data,
        "source_tools": ["get_ingest_health"],
        "source_relations": list(health.provenance.source_relations),
    }


def assemble_context(
    con: duckdb.DuckDBPyConnection,
    *,
    question: str,
    intent: str | None = None,
    sku: str | None = None,
) -> ContextBundle:
    """Build a typed context bundle for a bounded operational question."""
    resolved = resolve_intent(question, intent)
    target = extract_sku(question, sku)
    as_of = _utcnow()

    if resolved in ITEM_SCOPED:
        if not target:
            raise ValueError(f"sku is required for intent {resolved}")
        if resolved == "reprice_item":
            assembled = _reprice(con, target, resolved)
        elif resolved == "explain_attention":
            assembled = _explain_attention(con, target, resolved)
        elif resolved == "item_history":
            assembled = _item_history_intent(con, target, resolved)
        else:
            assembled = _item_state(con, target)
    elif resolved == "focus_today":
        assembled = _focus(con)
    elif resolved == "data_health":
        assembled = _health(con)
    elif resolved == "recent_changes":
        assembled = _recent_changes()
    else:
        raise ValueError(f"unhandled intent {resolved}")

    required = REQUIRED_CONCEPTS[resolved]
    extra_missing = []
    facts = assembled.get("facts") or {}
    if "snapshot" in required and "snapshot" not in facts:
        extra_missing.append(
            _missing("snapshot", "snapshot was not assembled", resolved)
        )
    if "attention_queue" in required and "attention" not in facts:
        extra_missing.append(
            _missing("attention_queue", "attention queue was not assembled", resolved)
        )
    if "warehouse_trust" in required and not (
        "trust" in facts
        or "ok" in facts
        or assembled.get("metrics", {}).get("warehouse_trust_ok") is not None
    ):
        extra_missing.append(
            _missing("warehouse_trust", "trust report was not assembled", resolved)
        )

    missing = list(assembled["missing"]) + extra_missing
    sufficient = not missing

    notes = [
        "FACT/DERIVED values come from typed business tools, not prompt memory.",
        "sufficient is rule-based: every required concept is present or listed in missing_context.",
        "retrieved_evidence is empty until unstructured retrieval exists.",
    ]
    if not sufficient:
        notes.append("Required context is incomplete — a copilot should abstain or qualify.")

    return ContextBundle(
        question=question,
        intent=resolved,
        as_of=as_of,
        objects=assembled["objects"],
        relationships=assembled["links"],
        facts=assembled["facts"],
        metrics=assembled["metrics"],
        events=assembled["events"],
        applicable_rules=assembled["rules"],
        retrieved_evidence=[],
        provenance={
            "tool": "assemble_context",
            "as_of": as_of,
            "source_tools": assembled.get("source_tools", []),
            "source_relations": assembled.get("source_relations", []),
            "metric_names": sorted(assembled.get("metrics") or {}),
            "notes": notes,
        },
        missing_context=missing,
        sufficient=sufficient,
    )
