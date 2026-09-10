"""FastAPI contracts for item business tools."""
from __future__ import annotations

import pytest

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def _build(con):
    for j in ALL_JOBS:
        j(con, db.data_dir()).run()


def test_api_item_and_history_contract(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    missing = client.get("/business/items/no-such-sku")
    assert missing.status_code == 404

    res = client.get("/business/items/stone-cargo-l")
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "fact"
    assert body["data"]["item"]["sku"] == "stone-cargo-l"
    assert body["data"]["listings"] == []
    assert body["provenance"]["tool"] == "get_item"
    assert "inventory_age_days" in body["provenance"]["metric_names"]

    hist = client.get("/business/items/j4-military-s/history")
    assert hist.status_code == 200
    hbody = hist.json()
    assert hbody["kind"] == "fact"
    assert hbody["data"]["sku"] == "j4-military-s"
    types = {row["type"] for row in hbody["data"]["timeline"]}
    assert "ordered" in types
    assert "listing_opened" in types
    assert hbody["provenance"]["tool"] == "get_item_history"


def test_api_snapshot_still_derived(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/business/snapshot")
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "derived"
    assert 40 <= body["data"]["items_total"] <= 80
    assert "margin" not in body["data"]


def test_api_channel_as_of_contract(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    missing = client.get("/business/channels/stockx")
    assert missing.status_code == 404

    before = client.get(
        "/business/channels/grailed", params={"as_of": "2025-06-01T00:00:00"}
    )
    assert before.status_code == 200
    body = before.json()
    assert body["kind"] == "fact"
    assert body["provenance"]["tool"] == "get_channel_as_of"
    assert len(body["data"]["versions"]) == 1
    assert body["data"]["versions"][0]["fee_pct"] == pytest.approx(0.09)

    after = client.get(
        "/business/channels/grailed", params={"as_of": "2026-06-01"}
    )
    assert after.status_code == 200
    assert after.json()["data"]["versions"][0]["fee_pct"] == pytest.approx(0.12)

    bad = client.get(
        "/business/channels/grailed", params={"as_of": "not-a-date"}
    )
    assert bad.status_code == 400


def test_api_context_bundle_contract(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get(
        "/context",
        params={
            "question": "Should I reprice stone-cargo-l?",
            "intent": "reprice_item",
            "sku": "stone-cargo-l",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "reprice_item"
    assert body["sufficient"] is False
    concepts = {row["concept"] for row in body["missing_context"]}
    assert "listing" in concepts
    assert body["provenance"]["tool"] == "assemble_context"


def test_api_context_accepts_intent_without_question(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/context", params={"intent": "focus_today"})
    assert res.status_code == 200
    body = res.json()
    assert body["intent"] == "focus_today"
    assert body["sufficient"] is True
    assert "snapshot" in body["facts"]


def test_api_eval_is_strict_twenty(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/eval")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 20
    assert body["passed"] == 20
    assert body["failed"] == 0
    assert body["skipped"] == 0
    assert body["ok"] is True


def test_api_eval_compare_keeps_engine_gold(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/eval/compare")
    assert res.status_code == 200
    body = res.json()
    assert body["engine"]["passed"] == 20
    assert body["engine"]["ok"] is True
    assert body["rag"]["total"] == 20
    assert "hybrid" in body["by_category"]
    hybrid = body["by_category"]["hybrid"]
    assert hybrid["rag_pass"] == hybrid["n"]
