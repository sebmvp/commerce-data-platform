"""Human-readable rendering of business payloads.

JSON (`--json`) stays the machine contract. This module is for terminals.
"""
from __future__ import annotations

from typing import Any

ACTION_LABELS = {
    "list_next": "LIST NEXT",
    "review_price_or_channel": "REVIEW PRICE OR CHANNEL",
    "consider_reprice": "CONSIDER REPRICE",
    "monitor": "MONITOR",
}

REASON_LABELS = {
    "unlisted_owned": "unlisted",
    "stale_listing": "stale listing",
    "high_attention_no_offers": "attention, no offers",
    "listed_active": "active listing",
}


def _num(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        if v.is_integer():
            return f"{int(v):,}"
        return f"{v:,.2f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def _row(label: str, value: str, width: int = 22) -> str:
    return f"  {label:<{width}} {value}"


def format_snapshot(data: dict[str, Any]) -> str:
    trust = "OK" if data.get("warehouse_trust_ok") else "ATTENTION NEEDED"
    lines = [
        "BUSINESS STATE",
        "",
        _row("Owned inventory", _num(data.get("capital_items"))),
        _row("Unlisted", _num(data.get("owned_unlisted"))),
        _row("Active listings", _num(data.get("active_listings"))),
        _row(
            "Stale listings",
            f"{_num(data.get('stale_active_listings'))}  "
            f"(≥ {data.get('stale_listing_days_threshold')} days)",
        ),
        _row("Completed sales", _num(data.get("orders"))),
        _row("Capital tied up", f"{_num(data.get('capital_tied_up_cny'))} CNY"),
        _row("Realized revenue", f"{_num(data.get('realized_revenue_usd'))} USD"),
        _row("Gross after fees", f"{_num(data.get('realized_gross_after_fees_usd'))} USD"),
        _row("", "not full margin"),
        _row("Warehouse trust", trust),
    ]
    reasons = data.get("warehouse_trust_reasons") or []
    for r in reasons:
        lines.append(f"    - {r}")
    return "\n".join(lines) + "\n"


def format_attention(data: dict[str, Any], *, limit: int = 5) -> str:
    recs = list(data.get("recommendations") or [])[:limit]
    lines = ["ATTENTION", ""]
    if not recs:
        lines.append("  (empty queue)")
        return "\n".join(lines) + "\n"

    for i, rec in enumerate(recs, 1):
        based = rec.get("based_on") or {}
        action = ACTION_LABELS.get(rec.get("action", ""), rec.get("action", ""))
        reason = REASON_LABELS.get(
            based.get("attention_reason", ""), based.get("attention_reason", "")
        )
        facts: list[str] = []
        if based.get("inventory_age_days") is not None:
            facts.append(f"held {_num(based['inventory_age_days'])} days")
        if based.get("listing_age_days") is not None:
            facts.append(f"listed {_num(based['listing_age_days'])} days")
        if based.get("acquisition_cost_cny") is not None:
            facts.append(f"acquisition {_num(based['acquisition_cost_cny'])} CNY")
        if based.get("watch_rate") is not None:
            facts.append(f"watch_rate {based['watch_rate']}")
        lines.append(f"  {i}. {rec.get('sku')}")
        lines.append(f"     {action}")
        if reason:
            lines.append(f"     {reason}")
        for fact in facts:
            lines.append(f"     {fact}")
        lines.append("")
    lines.append("  Heuristic recommendations. Facts are the numbers above.")
    return "\n".join(lines).rstrip() + "\n"


def format_trust(data: dict[str, Any]) -> str:
    status = "OK" if data.get("ok") else "ATTENTION NEEDED"
    lines = [
        "WAREHOUSE TRUST",
        "",
        _row("Status", status),
        _row("Rejected records", _num(data.get("total_rejected_records"))),
        _row("Failed runs", _num(data.get("failed_runs"))),
        _row("Orphaned runs", _num(data.get("orphaned_running"))),
        _row("Unbalanced", _num(data.get("unbalanced_success_runs"))),
    ]
    reasons = data.get("reasons") or []
    if reasons:
        lines.append("  Reasons")
        for r in reasons:
            lines.append(f"    - {r}")
    else:
        lines.append(_row("Alarms", "none"))
    return "\n".join(lines) + "\n"


def format_item(data: dict[str, Any]) -> str:
    item = data.get("item") or {}
    listings = data.get("listings") or []
    orders = data.get("orders") or []
    lines = [
        f"ITEM  {item.get('sku')}",
        "",
        _row("Product", str(item.get("product") or "—")),
        _row("Status", str(item.get("status") or "—")),
        _row("Condition", str(item.get("condition") or "—")),
        _row(
            "Acquisition",
            f"{_num(item.get('acquisition_cost_cny'))} CNY"
            + (
                f"  {item['acquisition_channel']}"
                if item.get("acquisition_channel")
                else ""
            ),
        ),
        _row("Acquired", str(item.get("acquired_at") or "—")),
        _row("Held", f"{_num(item.get('inventory_age_days'))} days"),
        _row("Target price", f"{_num(item.get('target_price_usd'))} USD"),
        _row("Listings", _num(len(listings))),
        _row("Orders", _num(len(orders))),
    ]
    for listing in listings:
        platform = listing.get("platform") or "channel"
        age = listing.get("listing_age_days")
        age_bit = f", {_num(age)} days" if age is not None else ""
        lines.append(
            f"    {platform}  {listing.get('status')}  "
            f"{_num(listing.get('price_usd'))} USD{age_bit}"
        )
    for order in orders:
        lines.append(
            f"    order {order.get('order_id')}  {order.get('status')}  "
            f"{_num(order.get('revenue_usd'))} USD"
        )
    return "\n".join(lines) + "\n"


def format_item_history(data: dict[str, Any]) -> str:
    lines = [
        f"ITEM HISTORY  {data.get('sku')}",
        "",
        _row("Status", str(data.get("status") or "—")),
        _row("Timeline", _num(len(data.get("timeline") or []))),
        _row("Engagement snaps", _num(len(data.get("engagement") or []))),
        "",
    ]
    for row in data.get("timeline") or []:
        at = str(row.get("at") or "—")
        if "T" in at:
            at = at.replace("T", " ", 1)
        detail = row.get("detail") or {}
        extra = ""
        if isinstance(detail, dict):
            platform = detail.get("platform")
            price = detail.get("price_usd") or detail.get("revenue_usd") or detail.get(
                "sold_price_usd"
            )
            bits = []
            if platform:
                bits.append(str(platform))
            if price is not None:
                bits.append(f"{_num(price)} USD")
            if bits:
                extra = "  " + "  ".join(bits)
        lines.append(f"  {at}  {row.get('type')}{extra}")
    if not data.get("timeline"):
        lines.append("  (no events)")
    return "\n".join(lines) + "\n"


def format_rejects(rows: list[tuple]) -> str:
    """rows: (error_code, n, sample_detail)."""
    lines = ["QUARANTINE", ""]
    if not rows:
        lines.append("  (no rejected records)")
        return "\n".join(lines) + "\n"
    for code, n, detail in rows:
        snippet = (detail or "").replace("\n", " ")
        if len(snippet) > 80:
            snippet = snippet[:77] + "..."
        lines.append(f"  {code:<22} {_num(n)}")
        if snippet:
            lines.append(f"    {snippet}")
    return "\n".join(lines) + "\n"
