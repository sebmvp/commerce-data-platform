"""Deterministic Context Engine evaluation (no LLM)."""
from __future__ import annotations

from typing import Any

from evals.context_questions import QUESTIONS


def score_case(bundle, case: dict[str, Any]) -> dict[str, Any]:
    if bundle is None or not case.get("implemented"):
        return {
            "id": case["id"],
            "category": case.get("category"),
            "question": case["question"],
            "implemented": False,
            "passed": False,
            "skipped": True,
            "errors": ["not implemented"],
            "expected": {
                "sufficient": case.get("expected_sufficient"),
                "missing": case.get("expected_missing"),
                "object_types": case.get("required_object_types"),
            },
            "actual": {"sufficient": None, "missing": [], "object_types": []},
        }
    missing = {m.concept for m in bundle.missing_context}
    types = {obj.type for obj in bundle.objects}
    expected_missing = set(case.get("expected_missing") or [])
    required_types = set(case.get("required_object_types") or [])
    unexpected_types = types - required_types - {
        "Item",
        "Listing",
        "Channel",
        "Order",
        "EngagementObservation",
        "IngestRun",
        "Recommendation",
        "Action",
    }
    errors: list[str] = []
    if case.get("implemented") and case.get("intent"):
        if bundle.intent != case["intent"]:
            errors.append(f"intent {bundle.intent!r} != {case['intent']!r}")
        if bundle.sufficient is not case["expected_sufficient"]:
            errors.append(
                f"sufficient {bundle.sufficient} != {case['expected_sufficient']}"
            )
        for concept in expected_missing:
            if concept not in missing:
                errors.append(f"missing_context lacked {concept!r}")
        for needed in required_types:
            if needed not in types:
                errors.append(f"missing object type {needed}")
        if case["expected_sufficient"] and bundle.missing_context:
            errors.append("expected no missing_context")
    elif not case.get("implemented"):
        errors.append("not implemented")
    return {
        "id": case["id"],
        "category": case.get("category"),
        "question": case["question"],
        "implemented": bool(case.get("implemented")),
        "passed": not errors if case.get("implemented") else False,
        "skipped": not case.get("implemented"),
        "errors": errors,
        "expected": {
            "sufficient": case.get("expected_sufficient"),
            "missing": case.get("expected_missing"),
            "object_types": case.get("required_object_types"),
        },
        "actual": {
            "sufficient": bundle.sufficient if case.get("implemented") else None,
            "missing": sorted(missing) if case.get("implemented") else [],
            "object_types": sorted(types) if case.get("implemented") else [],
        },
    }


def run_eval(con) -> dict[str, Any]:
    from cdp_cli.context import assemble_context

    results = []
    for case in QUESTIONS:
        if not case.get("implemented"):
            results.append(score_case(None, case))
            continue
        bundle = assemble_context(
            con,
            question=case["question"],
            intent=case["intent"],
            sku=case.get("sku"),
        )
        results.append(score_case(bundle, case))
    implemented = [r for r in results if r["implemented"]]
    passed = sum(1 for r in implemented if r["passed"])
    failed = [r for r in implemented if not r["passed"]]
    return {
        "total": len(QUESTIONS),
        "implemented": len(implemented),
        "passed": passed,
        "failed": len(failed),
        "skipped": len(QUESTIONS) - len(implemented),
        "ok": not failed,
        "cases": results,
    }
