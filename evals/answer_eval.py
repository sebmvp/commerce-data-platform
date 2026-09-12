"""Deterministic grounded-answer evaluation on the same ids as assemble_context.

This is not an LLM-as-judge. It checks the copilot contract against
FakeProvider (CI default): abstain when the bundle is insufficient,
cite only evidence_catalog refs, restate values that are in the bundle,
and do not emit prohibited claims.

A real model is optional (`make ai-smoke`) and is not required for this
report. Do not call this RAG and do not claim answer quality for GPT.
"""
from __future__ import annotations

from typing import Any


def _catalog(suite: str) -> list[dict[str, Any]]:
    if suite == "heldout":
        from evals.heldout_questions import HELD_OUT

        return HELD_OUT
    from evals.context_questions import QUESTIONS

    return QUESTIONS


def _suite_label(suite: str) -> str:
    return "HELD OUT" if suite == "heldout" else "GOLD / DEVELOPMENT"


def _scalar_needles(mapping: dict[str, Any] | None) -> list[str]:
    needles: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for inner in value.values():
                walk(inner)
            return
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, (list, tuple)):
            return
        if isinstance(value, (int, float)):
            needles.append(str(value))
        elif isinstance(value, str) and value.strip():
            needles.append(value)

    for value in (mapping or {}).values():
        walk(value)
    return needles


def score_answer_case(result: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """Score one ground_answer payload against a gold/held-out case."""
    errors: list[str] = []
    bundle = result.get("bundle") or {}
    catalog = set(bundle.get("evidence_catalog") or [])
    refs = list(result.get("evidence_refs") or [])
    answer = str(result.get("answer") or "")
    status = result.get("grounding_status")
    expected_sufficient = bool(case.get("expected_sufficient"))

    unknown = [ref for ref in refs if ref not in catalog]
    if unknown:
        errors.append("unknown citations: " + ", ".join(unknown))

    if expected_sufficient:
        if result.get("abstained"):
            errors.append("sufficient case abstained")
        if status != "grounded":
            errors.append(f"grounding_status {status!r} != 'grounded'")
        if not refs:
            errors.append("grounded answer cited no evidence")
        for typ in case.get("required_object_types") or []:
            prefix = f"object:{typ}:"
            if any(item.startswith(prefix) for item in catalog) and not any(
                item.startswith(prefix) for item in refs
            ):
                errors.append(f"did not cite required object type {typ}")
        needles = _scalar_needles(bundle.get("facts")) + _scalar_needles(
            bundle.get("metrics")
        )
        if needles and not any(needle in answer for needle in needles):
            errors.append("answer restated no bundle fact/metric values")
        sku = case.get("sku")
        if sku and sku not in answer and not any(sku in ref for ref in refs):
            errors.append(f"sku {sku} absent from answer and citations")
    else:
        if not result.get("abstained"):
            errors.append("insufficient case did not abstain")
        if status != "abstained":
            errors.append(f"grounding_status {status!r} != 'abstained'")

    answer_l = answer.lower()
    for claim in case.get("prohibited_claims") or []:
        token = str(claim).strip().lower()
        if token and token in answer_l:
            errors.append(f"prohibited claim {claim!r} in answer")

    return {
        "id": case["id"],
        "category": case.get("category"),
        "question": case["question"],
        "passed": not errors,
        "skipped": False,
        "errors": errors,
        "grounding_status": status,
        "abstained": result.get("abstained"),
        "evidence_refs": refs,
    }


def run_answer_eval(
    con,
    *,
    strict: bool = True,
    suite: str = "gold",
    questions: list[dict[str, Any]] | None = None,
    provider: Any | None = None,
) -> dict[str, Any]:
    from cdp_cli.llm import FakeProvider, ground_answer

    used = provider or FakeProvider()
    catalog = questions if questions is not None else _catalog(suite)
    results = []
    for case in catalog:
        result = ground_answer(
            con,
            question=case["question"],
            intent=case.get("intent"),
            sku=case.get("sku"),
            provider=used,
        )
        results.append(score_answer_case(result, case))
    failed = [row for row in results if not row["passed"]]
    skipped = [row for row in results if row["skipped"]]
    passed = sum(1 for row in results if row["passed"])
    ok = not failed and (not strict or not skipped)
    return {
        "suite": _suite_label(suite),
        "suite_id": suite,
        "layer": "grounded_answers",
        "provider": getattr(used, "name", type(used).__name__),
        "total": len(catalog),
        "passed": passed,
        "failed": len(failed),
        "skipped": len(skipped),
        "ok": ok,
        "strict": strict,
        "cases": results,
        "notes": (
            "Deterministic copilot contract on FakeProvider. "
            "Not an LLM-as-judge and not a claim about a paid model."
        ),
    }
