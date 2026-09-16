"""GET /search — deterministic Business Search over canonical tables."""
from __future__ import annotations

import pytest

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


def _build(con):
    for j in ALL_JOBS:
        j(con, db.data_dir()).run()


def test_search_finds_items_and_is_grouped(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/search", params={"q": "stone"})
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "stone"
    types = [g["type"] for g in body["groups"]]
    assert set(types) == {"Item", "Listing", "Order", "Note"}
    items = next(g for g in body["groups"] if g["type"] == "Item")["hits"]
    cargo = [h for h in items if h["sku"] == "stone-cargo-l"]
    assert cargo, "expected the cargo pants item in results"
    hit = cargo[0]
    assert "Cargo" in hit["label"]
    assert hit["href"] == "/inventory/stone-cargo-l"
    # Product label, not raw SKU, is the human label
    assert hit["label"].startswith("Stone Island")
    assert not hit["label"].startswith("stone-cargo")


def test_search_empty_query_returns_empty_groups(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/search", params={"q": ""})
    assert res.status_code == 200
    body = res.json()
    assert all(not g["hits"] for g in body["groups"])


def test_search_no_match_returns_empty_hits(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/search", params={"q": "zzzzzzz"})
    assert res.status_code == 200
    assert all(not g["hits"] for g in res.json()["groups"])


def test_search_hits_listing_and_order(warehouse):
    _build(warehouse)
    warehouse.close()
    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    res = client.get("/search", params={"q": "jordan"})
    body = res.json()
    listings = next(g for g in body["groups"] if g["type"] == "Listing")["hits"]
    orders = next(g for g in body["groups"] if g["type"] == "Order")["hits"]
    assert listings, "expected listing hits for jordan"
    assert listings[0]["href"].startswith("/inventory/")
    assert orders, "expected order hits for jordan"
    # channel names are humanized, not raw relational keys
    for order in orders:
        meta = order["meta"]
        assert "@" not in meta
        assert "/" not in meta.split("·")[0]
