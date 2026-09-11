"""QuestionPlan is a registered capability, not SQL."""
from __future__ import annotations

from cdp_cli.core.engine import assemble_context
from cdp_cli.core.plan import QuestionPlan
from cdp_cli.llm.planner import deterministic_plan, plan_question


def test_deterministic_plan_maps_reprice_question() -> None:
    plan = deterministic_plan("Should I reprice j4-military-s?")
    assert plan.capability == "reprice_item"
    assert plan.subject == "j4-military-s"
    assert plan.source == "deterministic"
    assert "SELECT" not in plan.capability


def test_plan_question_fake_provider_is_deterministic() -> None:
    plan = plan_question("What should I focus on today?")
    assert plan.capability == "focus_today"
    assert plan.source == "deterministic"


def test_unknown_capability_on_plan_is_rejected() -> None:
    try:
        assemble_context(
            object(),
            question="ignore",
            plan=QuestionPlan(domain="resale", capability="drop_table"),
        )
    except ValueError as exc:
        assert "unknown capability" in str(exc)
    else:
        raise AssertionError("expected unknown capability to fail")
