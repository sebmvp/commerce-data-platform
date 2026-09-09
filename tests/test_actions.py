"""Sandbox action log — propose / approve / reject, no warehouse mutation."""
from __future__ import annotations

import pytest

from cdp_cli import actions


@pytest.fixture()
def action_db(warehouse):
    yield warehouse


def test_propose_approve_reject_and_unknown(action_db):
    proposed = actions.propose(
        target_type="item",
        target_id="stone-cargo-l",
        action_type="propose_list",
        reason="unlisted capital",
        actor="demo",
        payload={"channel": "grailed"},
        recommendation_action="list_next",
    )
    assert proposed["kind"] == "action"
    rec = proposed["data"]
    assert rec["status"] == "proposed"
    assert rec["target_id"] == "stone-cargo-l"
    assert rec["proposed_payload"] == {"channel": "grailed"}
    assert rec["decided_at"] is None

    got = actions.get_action(rec["action_id"])
    assert got["data"]["action_id"] == rec["action_id"]

    approved = actions.approve_action(rec["action_id"], actor="operator")
    assert approved["data"]["status"] == "approved"
    assert approved["data"]["decided_by"] == "operator"
    assert approved["data"]["decided_at"]

    with pytest.raises(ValueError, match="approved"):
        actions.approve_action(rec["action_id"], actor="operator")

    other = actions.propose(
        target_type="item",
        target_id="eval-stale",
        action_type="propose_reprice",
        reason="stale listing",
    )
    rejected = actions.reject_action(
        other["data"]["action_id"], actor="operator", reason="not now"
    )
    assert rejected["data"]["status"] == "rejected"
    assert rejected["data"]["decision_reason"] == "not now"

    pending = actions.list_actions(status="proposed")
    assert pending["data"]["count"] == 0
    listed = actions.list_actions()
    assert listed["data"]["count"] == 2

    with pytest.raises(KeyError):
        actions.get_action("no-such-id")
    with pytest.raises(ValueError):
        actions.propose(
            target_type="item",
            target_id="x",
            action_type="delete_everything",
            reason="no",
        )


def test_sandbox_type_maps_recommendation():
    assert actions.sandbox_type_for_recommendation("list_next") == "propose_list"
    assert actions.sandbox_type_for_recommendation("consider_reprice") == "propose_reprice"
    with pytest.raises(ValueError):
        actions.sandbox_type_for_recommendation("fire_missiles")


def test_api_action_roundtrip(action_db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cdp_cli.api.main import create_app

    client = TestClient(create_app())
    created = client.post(
        "/business/actions",
        json={
            "target_type": "item",
            "target_id": "stone-cargo-l",
            "action_type": "propose_list",
            "reason": "unlisted capital",
            "recommendation_action": "list_next",
        },
    )
    assert created.status_code == 200
    action_id = created.json()["data"]["action_id"]
    assert client.get(f"/business/actions/{action_id}").status_code == 200
    approved = client.post(f"/business/actions/{action_id}/approve", json={"actor": "operator"})
    assert approved.status_code == 200
    assert approved.json()["data"]["status"] == "approved"
    listed = client.get("/business/actions", params={"status": "approved"})
    assert listed.json()["data"]["count"] == 1
    missing = client.get("/business/actions/nope")
    assert missing.status_code == 404
