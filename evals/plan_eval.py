"""Question/tool planning eval. Separate from context assembly and grounding."""
from __future__ import annotations

from typing import Any

from cdp_cli.llm.planner import deterministic_plan


def _catalog(suite: str) -> list[dict[str, Any]]:
    if suite == "heldout":
        from evals.heldout_questions import HELD_OUT

        return HELD_OUT
    from evals.context_questions import QUESTIONS

    return QUESTIONS


def run_plan_eval(con, *, suite: str = "gold") -> dict[str, Any]:
    del con
    catalog = _catalog(suite)
    cases = []
    for case in catalog:
        errors: list[str] = []
        try:
            plan = deterministic_plan(case["question"], subject=case.get("sku"))
        except ValueError as exc:
            cases.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "passed": False,
                    "skipped": False,
                    "errors": [str(exc)],
                    "capability": None,
                    "subject": None,
                    "source": "deterministic",
                }
            )
            continue
        expected = case.get("intent")
        if expected and plan.capability != expected:
            errors.append(f"capability {plan.capability!r} != {expected!r}")
        if case.get("sku") and plan.subject and plan.subject != case["sku"]:
            errors.append(f"subject {plan.subject!r} != {case['sku']!r}")
        cases.append(
            {
                "id": case["id"],
                "question": case["question"],
                "passed": not errors,
                "skipped": False,
                "errors": errors,
                "capability": plan.capability,
                "subject": plan.subject,
                "source": plan.source,
            }
        )
    failed = [row for row in cases if not row["passed"]]
    passed = sum(1 for row in cases if row["passed"])
    return {
        "suite": "HELD OUT" if suite == "heldout" else "GOLD / DEVELOPMENT",
        "suite_id": suite,
        "layer": "question_tool_planning",
        "total": len(catalog),
        "passed": passed,
        "failed": len(failed),
        "skipped": 0,
        "ok": not failed,
        "cases": cases,
        "notes": (
            "Deterministic capability mapping. Not combined with grounding "
            "or assembly into an accuracy score."
        ),
    }
