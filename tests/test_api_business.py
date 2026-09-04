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
    assert body["data"]["items_total"] == 12
    assert "margin" not in body["data"]
