"""Adversarial grounding: fail closed, never manufacture citations."""
from __future__ import annotations

import json

from cdp_cli import db
from cdp_cli.core.model import ContextBundle, ContextObject
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.llm import ScriptedProvider, ground_answer, parse_grounded


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def _tiny_bundle() -> ContextBundle:
    return ContextBundle(
        question="q",
        intent="item_state",
        as_of="2026-09-09T12:00:00",
        objects=[ContextObject("Item", "j4-military-s", {"sku": "j4-military-s"})],
        facts={"sku": "j4-military-s"},
        metrics={"watch_rate": 0.1},
        sufficient=True,
    )


def test_malformed_json_is_invalid() -> None:
    result = parse_grounded("not json", _tiny_bundle())
    assert result["ok"] is False
    assert "malformed" in result["reason"]


def test_valid_json_without_citations_is_invalid() -> None:
    raw = json.dumps(
        {
            "answer": "reprice it",
            "abstained": False,
            "evidence_refs": [],
        }
    )
    result = parse_grounded(raw, _tiny_bundle())
    assert result["ok"] is False
    assert "cited no evidence" in result["reason"]


def test_hallucinated_citation_is_invalid() -> None:
    raw = json.dumps(
        {
            "answer": "reprice it",
            "abstained": False,
            "evidence_refs": ["object:Item:does-not-exist"],
        }
    )
    result = parse_grounded(raw, _tiny_bundle())
    assert result["ok"] is False
    assert "unknown evidence refs" in result["reason"]


def test_mixed_valid_and_invalid_citations_are_invalid() -> None:
    raw = json.dumps(
        {
            "answer": "ok",
            "abstained": False,
            "evidence_refs": ["object:Item:j4-military-s", "metric:invented"],
        }
    )
    result = parse_grounded(raw, _tiny_bundle())
    assert result["ok"] is False
    assert "metric:invented" in result["reason"]


def test_nonexistent_action_type_is_invalid() -> None:
    raw = json.dumps(
        {
            "answer": "do it",
            "abstained": False,
            "evidence_refs": ["object:Item:j4-military-s"],
            "suggested_action": {"action_type": "launch_missiles"},
        }
    )
    result = parse_grounded(raw, _tiny_bundle())
    assert result["ok"] is False
    assert "action_type" in result["reason"]


def test_invalid_action_payload_is_invalid() -> None:
    raw = json.dumps(
        {
            "answer": "cut",
            "abstained": False,
            "evidence_refs": ["object:Item:j4-military-s"],
            "suggested_action": {
                "action_type": "propose_reprice",
                "payload": {"new_price_usd": 99},
            },
        }
    )
    result = parse_grounded(raw, _tiny_bundle())
    assert result["ok"] is False
    assert "numeric price" in result["reason"]


def test_extra_fields_are_invalid() -> None:
    raw = json.dumps(
        {
            "answer": "ok",
            "abstained": False,
            "evidence_refs": ["object:Item:j4-military-s"],
            "secret_sql": "DROP TABLE catalog.items",
        }
    )
    result = parse_grounded(raw, _tiny_bundle())
    assert result["ok"] is False
    assert "schema" in result["reason"]


def test_valid_citations_pass() -> None:
    raw = json.dumps(
        {
            "answer": "listing is stale",
            "abstained": False,
            "evidence_refs": ["object:Item:j4-military-s", "metric:watch_rate"],
            "caveats": [],
        }
    )
    result = parse_grounded(raw, _tiny_bundle())
    assert result["ok"] is True
    assert result["evidence_refs"] == [
        "object:Item:j4-military-s",
        "metric:watch_rate",
    ]


def test_insufficient_context_does_not_call_provider(warehouse) -> None:
    _build(warehouse)

    class Boom(ScriptedProvider):
        def complete(self, prompt: str) -> str:
            raise AssertionError("provider must not run when insufficient")

    result = ground_answer(
        warehouse,
        question="Should I reprice stone-cargo-l?",
        provider=Boom("unused"),
    )
    assert result["abstained"] is True
    assert result["grounding_status"] == "abstained"


def test_provider_failure_is_invalid(warehouse) -> None:
    _build(warehouse)
    result = ground_answer(
        warehouse,
        question="Should I reprice j4-military-s?",
        provider=ScriptedProvider(RuntimeError("timeout")),
    )
    assert result["grounding_status"] == "invalid"
    assert result["abstained"] is True
    assert "provider failure" in result["invalid_reason"]


def test_malformed_output_does_not_become_trusted_answer(warehouse) -> None:
    _build(warehouse)
    result = ground_answer(
        warehouse,
        question="Should I reprice j4-military-s?",
        provider=ScriptedProvider("lol this is prose"),
    )
    assert result["grounding_status"] == "invalid"
    assert result["abstained"] is True
    assert "lol this is prose" not in result["answer"]
    assert result["untrusted_output"] == "lol this is prose"


def test_does_not_manufacture_citations_on_empty_refs(warehouse) -> None:
    _build(warehouse)
    raw = json.dumps(
        {
            "answer": "cut the price",
            "abstained": False,
            "evidence_refs": [],
        }
    )
    result = ground_answer(
        warehouse,
        question="Should I reprice j4-military-s?",
        provider=ScriptedProvider(raw),
    )
    assert result["grounding_status"] == "invalid"
    assert result["evidence_refs"] == []
