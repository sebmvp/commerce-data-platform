"""Context engine — assemble a typed bundle, not a SQL dump.

The engine talks in objects/links/events/rules. Missing required
context must be explicit. Sufficiency is rule-based, not a score.
"""
from __future__ import annotations

import pytest

from cdp_cli import db
from cdp_cli.core import assemble_context
from cdp_cli.ingest import ALL_JOBS


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_reprice_listed_item_is_sufficient(warehouse):
    _build(warehouse)
    bundle = assemble_context(
        warehouse,
        question="Should I reprice j4-military-s?",
        sku="j4-military-s",
    )
    assert bundle.intent == "reprice_item"
    assert bundle.sufficient is True
    assert bundle.missing_context == []

    types = {obj.type for obj in bundle.objects}
    assert "Item" in types
    assert "Listing" in types
    assert "Channel" in types

    item = next(o for o in bundle.objects if o.type == "Item")
    assert item.id == "j4-military-s"
    assert item.properties["status"] == "listed"
    assert item.properties["acquisition_cost_cny"] == 4181

    link_types = {link.type for link in bundle.relationships}
    assert "HAS_LISTING" in link_types
    assert "ON_CHANNEL" in link_types
    assert "HAS_ENGAGEMENT" in link_types

    assert "listing_age_days" in bundle.metrics
    assert "watch_rate" in bundle.metrics
    assert "inventory_age_days" in bundle.metrics
    assert bundle.metrics["watch_rate"] is not None

    rule_names = {rule["name"] for rule in bundle.applicable_rules}
    assert "stale_listing" in rule_names
    assert "high_attention_no_offers" in rule_names

    assert bundle.events
    assert bundle.provenance["tool"] == "assemble_context"
    assert "get_item" in bundle.provenance["source_tools"]
    assert bundle.retrieved_evidence
    assert all("body" in ev and ev.get("kind") for ev in bundle.retrieved_evidence)


def test_reprice_unlisted_item_reports_missing_listing(warehouse):
    _build(warehouse)
    bundle = assemble_context(
        warehouse,
        question="Should I reprice stone-cargo-l?",
        intent="reprice_item",
        sku="stone-cargo-l",
    )
    assert bundle.intent == "reprice_item"
    assert bundle.sufficient is False
    concepts = {m.concept for m in bundle.missing_context}
    assert "listing" in concepts
    assert "engagement" in concepts
    assert "acquisition_cost" not in concepts
    types = {obj.type for obj in bundle.objects}
    assert "Item" in types
    assert "Listing" not in types


def test_reprice_without_engagement_snapshots_is_insufficient(warehouse):
    warehouse.execute(
        """
        INSERT INTO core.channels
          (channel_key, platform, handle, standing, fee_pct, valid_from)
        VALUES ('grailed/ctx@0', 'grailed', 'ctx', 'active', 0.09,
                TIMESTAMP '2020-01-01')
        """
    )
    warehouse.execute(
        """
        INSERT INTO catalog.items
          (item_id, sku, product, acquisition_cost_cny, status, qty)
        VALUES ('ctx-no-eng', 'ctx-no-eng', 'No Eng', 1000, 'listed', 1)
        """
    )
    warehouse.execute(
        """
        INSERT INTO catalog.item_events
          (event_id, item_id, event_type, event_at)
        VALUES ('ev-ctx-no-eng', 'ctx-no-eng', 'received',
                current_timestamp - INTERVAL '20' DAY)
        """
    )
    warehouse.execute(
        """
        INSERT INTO sales.listings
          (listing_id, item_id, channel_key, price_usd, status, listed_at)
        VALUES ('lst-ctx-no-eng', 'ctx-no-eng', 'grailed/ctx@0', 150, 'active',
                current_timestamp - INTERVAL '10' DAY)
        """
    )
    bundle = assemble_context(
        warehouse,
        question="Should I reprice ctx-no-eng?",
        sku="ctx-no-eng",
    )
    assert bundle.sufficient is False
    concepts = {m.concept for m in bundle.missing_context}
    assert "engagement" in concepts
    assert "listing" not in concepts
    types = {obj.type for obj in bundle.objects}
    assert "Listing" in types
    assert "EngagementObservation" not in types


def test_focus_today_includes_snapshot_attention_and_trust(warehouse):
    _build(warehouse)
    bundle = assemble_context(
        warehouse,
        question="What should I focus on today?",
    )
    assert bundle.intent == "focus_today"
    assert bundle.sufficient is True
    assert "snapshot" in bundle.facts
    assert "attention" in bundle.facts
    assert "trust" in bundle.facts
    assert 40 <= bundle.facts["snapshot"]["items_total"] <= 80
    assert bundle.metrics["warehouse_trust_ok"] is True
    rec_types = {obj.type for obj in bundle.objects}
    assert "Recommendation" in rec_types
    assert any(link.type == "TARGETS" for link in bundle.relationships)


def test_explain_attention_for_unlisted_item(warehouse):
    _build(warehouse)
    bundle = assemble_context(
        warehouse,
        question="Why is stone-cargo-l in the attention queue?",
        sku="stone-cargo-l",
    )
    assert bundle.intent == "explain_attention"
    assert bundle.facts["attention_reason"] == "unlisted_owned"
    assert bundle.facts["action"] == "list_next"
    assert bundle.sufficient is True


def test_unknown_intent_is_rejected(warehouse):
    with pytest.raises(ValueError, match="unknown intent"):
        assemble_context(
            warehouse,
            question="hello",
            intent="teleport_inventory",
        )


def test_question_extracts_sku_when_not_passed(warehouse):
    _build(warehouse)
    bundle = assemble_context(
        warehouse,
        question="Should I reprice j4-military-s?",
    )
    assert bundle.intent == "reprice_item"
    assert bundle.facts["sku"] == "j4-military-s"
