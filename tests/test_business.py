"""Business decision surface + metric definitions."""
from __future__ import annotations

import pytest

from cdp_cli import db, metrics
from cdp_cli.business import (
    explain_metric,
    get_business_snapshot,
    get_ingest_health,
    get_inventory_attention_queue,
)
from cdp_cli.ingest import ALL_JOBS


def _build(con):
    for j in ALL_JOBS:
        j(con, db.data_dir()).run()


def test_metric_catalog_is_nonempty_and_stable():
    cat = metrics.metric_catalog()
    names = {m["name"] for m in cat}
    assert "capital_tied_up_cny" in names
    assert "inventory_age_days" in names
    assert "stale_listing" in names
    # Full margin must not be silently claimed.
    assert "realized_margin" not in names
    m = metrics.get_metric("realized_gross_after_fees_usd")
    assert "NOT full margin" in m.definition or "NOT full margin" in m.limitations


def test_explain_metric_unknown():
    with pytest.raises(KeyError):
        explain_metric("not_a_real_metric")


def test_business_snapshot_counts(warehouse):
    _build(warehouse)
    payload = get_business_snapshot(warehouse)
    assert payload.kind == "derived"
    d = payload.data
    assert d["items_total"] == 12
    assert d["owned_unlisted"] >= 1
    assert d["capital_tied_up_cny"] > 0
    assert d["warehouse_trust_ok"] is True
    assert "capital_tied_up_cny" in payload.provenance.metric_names
    # Must not claim full margin field.
    assert "margin" not in d


def test_attention_queue_labels_reasons_and_recommendations(warehouse):
    _build(warehouse)
    payload = get_inventory_attention_queue(warehouse, limit=10)
    assert payload.kind == "recommendation"
    queue = payload.data["queue"]
    assert len(queue) >= 1
    reasons = {r["attention_reason"] for r in queue}
    # Sample data has owned unlisted items.
    assert "unlisted_owned" in reasons
    for row in queue:
        assert "sku" in row
        assert row["attention_reason"] in {
            "unlisted_owned",
            "stale_listing",
            "high_attention_no_offers",
            "listed_active",
        }
    recs = payload.data["recommendations"]
    assert recs
    assert recs[0]["action"] in {
        "list_next",
        "review_price_or_channel",
        "consider_reprice",
        "monitor",
    }
    assert "based_on" in recs[0]


def test_attention_prioritizes_unlisted_before_active(warehouse):
    _build(warehouse)
    payload = get_inventory_attention_queue(warehouse, limit=25)
    queue = payload.data["queue"]
    # First unlisted should appear before any listed_active-only rows when both exist.
    statuses = [r["attention_reason"] for r in queue]
    if "unlisted_owned" in statuses and "listed_active" in statuses:
        assert statuses.index("unlisted_owned") < statuses.index("listed_active")


def test_ingest_health_tool(warehouse):
    _build(warehouse)
    payload = get_ingest_health(warehouse)
    assert payload.kind == "fact"
    assert payload.data["ok"] is True
