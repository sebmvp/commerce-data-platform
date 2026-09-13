"""Analyst task-success eval. Separate from assembly, planning, and grounding."""
from __future__ import annotations

from typing import Any

from evals.answer_eval import score_answer_case


def _catalog(suite: str) -> list[dict[str, Any]]:
    if suite == "heldout":
        from evals.heldout_questions import HELD_OUT

        return HELD_OUT
    from evals.context_questions import QUESTIONS

    return QUESTIONS


def run_analyst_eval(
    con,
    *,
    suite: str = "gold",
    strict: bool = True,
) -> dict[str, Any]:
    from cdp_cli.llm import FakeProvider, run_analyst

    used = FakeProvider()
    catalog = _catalog(suite)
    results = []
    for case in catalog:
        try:
            result = run_analyst(
                con,
                question=case["question"],
                sku=case.get("sku"),
                provider=used,
            )
        except (KeyError, ValueError) as exc:
            results.append(
                {
                    "id": case["id"],
                    "category": case.get("category"),
                    "question": case["question"],
                    "passed": False,
                    "skipped": False,
                    "errors": [str(exc)],
                    "grounding_status": None,
                    "abstained": None,
                    "evidence_refs": [],
                    "tool_trace": [],
                }
            )
            continue
        scored = score_answer_case(result, case)
        errors = list(scored["errors"])
        traces = result.get("tool_trace") or []
        if not traces:
            errors.append("analyst produced no tool trace")
        allowed = _allowed()
        bad = [t.get("tool") for t in traces if t.get("tool") not in allowed]
        if bad:
            errors.append("unregistered tools: " + ", ".join(str(x) for x in bad))
        if result.get("bundle") is None:
            errors.append("analyst result missing exact bundle")
        scored["errors"] = errors
        scored["passed"] = not errors
        scored["tool_trace"] = [t.get("summary") for t in traces]
        results.append(scored)
    failed = [row for row in results if not row["passed"]]
    skipped = [row for row in results if row["skipped"]]
    passed = sum(1 for row in results if row["passed"])
    ok = not failed and (not strict or not skipped)
    return {
        "suite": "HELD OUT" if suite == "heldout" else "GOLD / DEVELOPMENT",
        "suite_id": suite,
        "layer": "agent_task_success",
        "provider": "fake",
        "total": len(catalog),
        "passed": passed,
        "failed": len(failed),
        "skipped": len(skipped),
        "ok": ok,
        "strict": strict,
        "cases": results,
        "notes": (
            "FakeProvider analyst contract: registered tools only, exact bundle "
            "returned, grounding still fail-closed. Not an LLM-as-judge."
        ),
    }


def _allowed() -> set[str]:
    from cdp_cli.llm.analyst import registered_tools

    return set(registered_tools())
