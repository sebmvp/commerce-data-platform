"""Typed evidence units and fail-closed citations."""
from __future__ import annotations

from cdp_cli.core.model import ContextBundle, ContextEvent, ContextObject


def test_evidence_units_are_typed_and_stable() -> None:
    bundle = ContextBundle(
        question="q",
        intent="item_state",
        as_of="2026-09-09T12:00:00",
        objects=[ContextObject("Item", "j4-military-s", {"sku": "j4-military-s"})],
        facts={"sku": "j4-military-s", "acquisition_cost_cny": 4800},
        metrics={"watch_rate": 0.1},
        events=[
            ContextEvent(
                type="price_change",
                at="2026-08-01T00:00:00",
                object_ref="Listing:abc",
                source="listing_events",
            )
        ],
        applicable_rules=[{"name": "stale_listing", "definition": "age", "policy_version": "v1"}],
        applicable_policies=[
            {
                "id": "resale.decision.price-review",
                "version": "v1",
                "title": "Price review",
                "summary": "REVIEW PRICE",
            }
        ],
        retrieved_evidence=[
            {
                "note_id": "condition-note",
                "title": "condition",
                "body": "scuff",
                "object_type": "Item",
                "object_id": "j4-military-s",
            }
        ],
        sufficient=True,
    )
    units = {u.ref: u for u in bundle.evidence_units()}
    assert units["object:Item:j4-military-s"].kind == "object"
    assert "fact:j4-military-s:acquisition_cost_cny" in units
    assert units["fact:j4-military-s:acquisition_cost_cny"].kind == "fact"
    assert "metric:j4-military-s:watch_rate" in units
    assert units["metric:watch_rate"].kind == "metric"
    assert any(ref.startswith("event:") and "price_change" in ref for ref in units)
    assert "rule:resale.decision.price-review:v1" in units
    assert "note:j4-military-s:condition-note" in units
    catalog = bundle.citeable_refs()
    assert catalog["fact:sku"] == "fact"
    payload = bundle.to_dict()
    assert "evidence_units" in payload
    assert set(payload["evidence_catalog"]) == set(catalog)


def test_citeable_refs_do_not_invent_keys() -> None:
    bundle = ContextBundle(question="q", intent="data_health", as_of="now")
    assert bundle.citeable_refs() == {}
    assert bundle.to_dict()["evidence_catalog"] == []
