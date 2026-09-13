"""Analyst Agent: registered tools only, bounded loop, exact bundle."""
from __future__ import annotations

import json

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.llm import FakeProvider, ScriptedProvider, run_analyst
from cdp_cli.llm.analyst import MAX_ITERATIONS, REGISTERED_TOOLS


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_registered_tools_are_read_only() -> None:
    assert "sql" not in REGISTERED_TOOLS
    assert "python" not in REGISTERED_TOOLS
    assert MAX_ITERATIONS <= 5


def test_broad_question_uses_multiple_read_tools(warehouse) -> None:
    _build(warehouse)
    result = run_analyst(
        warehouse, question="What should I focus on today?", provider=FakeProvider()
    )
    tools = [t["tool"] for t in result["tool_trace"]]
    assert "business_snapshot" in tools
    assert "attention_queue" in tools
    assert "data_health" in tools
    assert result["bundle"]["question"]
    assert result["provider"] == "fake"
    assert result["real_model"] is False


def test_item_question_narrows_to_subject(warehouse) -> None:
    _build(warehouse)
    result = run_analyst(
        warehouse,
        question="Should I reprice j4-military-s?",
        provider=FakeProvider(),
    )
    assert result["plan"]["capability"] == "reprice_item"
    assert result["plan"]["subject"] == "j4-military-s"
    assert result["bundle"] is result["bundle"]
    assert result["grounding_status"] in {"grounded", "abstained", "invalid"}
    assert all(
        ref in result["bundle"]["evidence_catalog"] for ref in result["evidence_refs"]
    )


def test_unknown_tool_is_not_executed(warehouse) -> None:
    _build(warehouse)

    class LoopThenAnswer(ScriptedProvider):
        name = "openai_compatible"
        model = "scripted"
        calls = 0

        def complete(self, prompt: str) -> str:
            self.calls += 1
            if "registered_tools:" in prompt:
                return json.dumps(
                    {
                        "action": "call",
                        "tools": [{"name": "drop_table", "subject": None}],
                    }
                )
            return json.dumps(
                {
                    "answer": "ok",
                    "abstained": False,
                    "evidence_refs": ["object:Item:j4-military-s"],
                }
            )

    result = run_analyst(
        warehouse,
        question="Should I reprice j4-military-s?",
        provider=LoopThenAnswer("unused"),
    )
    assert any(t["tool"] == "drop_table" and t["ok"] is False for t in result["tool_trace"])


def test_iteration_limit(warehouse) -> None:
    _build(warehouse)

    class AlwaysMore(ScriptedProvider):
        name = "openai_compatible"
        model = "scripted"

        def complete(self, prompt: str) -> str:
            if "registered_tools:" in prompt:
                return json.dumps(
                    {
                        "action": "call",
                        "tools": [{"name": "data_health", "subject": None}],
                    }
                )
            return json.dumps(
                {
                    "answer": "ok",
                    "abstained": False,
                    "evidence_refs": ["object:Item:j4-military-s"],
                }
            )

    result = run_analyst(
        warehouse,
        question="Should I reprice j4-military-s?",
        provider=AlwaysMore("unused"),
        max_iterations=3,
    )
    assert result["iterations"] <= 3
    assert result["max_iterations"] == 3


def test_followup_why_reuses_subject(warehouse) -> None:
    _build(warehouse)
    first = run_analyst(
        warehouse,
        question="What should I focus on today?",
        provider=FakeProvider(),
    )
    second = run_analyst(
        warehouse,
        question="Why?",
        provider=FakeProvider(),
        history=[first],
    )
    assert second["resolved_question"] != "Why?"


def test_insufficient_still_abstains(warehouse) -> None:
    _build(warehouse)
    result = run_analyst(
        warehouse,
        question="Should I reprice stone-cargo-l?",
        provider=FakeProvider(),
    )
    assert result["abstained"] is True
    assert result["grounding_status"] == "abstained"
    assert result["bundle"]["sufficient"] is False
