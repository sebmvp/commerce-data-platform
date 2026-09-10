"""Deterministic Context Engine evaluation (no LLM)."""
from __future__ import annotations

from typing import Any

from evals.context_questions import QUESTIONS


def score_case(bundle, case: dict[str, Any]) -> dict[str, Any]:
    if bundle is None:
        return {
            "id": case["id"],
            "category": case.get("category"),
            "question": case["question"],
            "passed": False,
            "skipped": False,
            "errors": ["bundle was not assembled"],
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
    errors: list[str] = []
    if case.get("intent") and bundle.intent != case["intent"]:
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
    unexpected = []
    if case.get("max_objects") is not None and len(bundle.objects) > case["max_objects"]:
        unexpected.append(
            f"object bloat {len(bundle.objects)} > {case['max_objects']}"
        )
        errors.extend(unexpected)
    return {
        "id": case["id"],
        "category": case.get("category"),
        "question": case["question"],
        "passed": not errors,
        "skipped": False,
        "errors": errors,
        "expected": {
            "sufficient": case.get("expected_sufficient"),
            "missing": case.get("expected_missing"),
            "object_types": case.get("required_object_types"),
        },
        "actual": {
            "sufficient": bundle.sufficient,
            "missing": sorted(missing),
            "object_types": sorted(types),
        },
    }


def run_eval(con, *, strict: bool = True) -> dict[str, Any]:
    from cdp_cli.context import assemble_context

    results = []
    for case in QUESTIONS:
        bundle = assemble_context(
            con,
            question=case["question"],
            intent=case.get("intent"),
            sku=case.get("sku"),
        )
        results.append(score_case(bundle, case))
    passed = sum(1 for r in results if r["passed"])
    failed = [r for r in results if not r["passed"]]
    skipped = [r for r in results if r["skipped"]]
    ok = not failed and (not strict or not skipped)
    return {
        "total": len(QUESTIONS),
        "passed": passed,
        "failed": len(failed),
        "skipped": len(skipped),
        "ok": ok,
        "strict": strict,
        "cases": results,
    }


def run_compare(con, *, strict: bool = True) -> dict[str, Any]:
    """Engine vs lexical RAG on the same gold ids. RAG is not the product path."""
    from evals.rag_baseline import run_rag_eval

    engine = run_eval(con, strict=strict)
    rag = run_rag_eval(con)
    cases = []
    for e_case, r_case in zip(engine["cases"], rag["cases"], strict=True):
        if e_case["id"] != r_case["id"]:
            raise RuntimeError(
                f"eval id mismatch {e_case['id']} vs {r_case['id']}"
            )
        if e_case["passed"] and r_case["passed"]:
            winner = "tie"
        elif e_case["passed"]:
            winner = "engine"
        elif r_case["passed"]:
            winner = "rag"
        else:
            winner = "both_fail"
        cases.append(
            {
                "id": e_case["id"],
                "category": e_case.get("category"),
                "question": e_case["question"],
                "engine": e_case["passed"],
                "rag": r_case["passed"],
                "winner": winner,
                "engine_errors": e_case.get("errors") or [],
                "rag_errors": r_case.get("errors") or [],
            }
        )
    by_category: dict[str, dict[str, int]] = {}
    for case in cases:
        cat = by_category.setdefault(
            case["category"] or "unknown",
            {"n": 0, "engine_pass": 0, "rag_pass": 0},
        )
        cat["n"] += 1
        cat["engine_pass"] += int(case["engine"])
        cat["rag_pass"] += int(case["rag"])
    return {
        "engine": {
            "total": engine["total"],
            "passed": engine["passed"],
            "failed": engine["failed"],
            "ok": engine["ok"],
        },
        "rag": {
            "total": rag["total"],
            "passed": rag["passed"],
            "failed": rag["failed"],
            "ok": rag["ok"],
            "corpus_size": rag.get("corpus_size"),
            "k": rag.get("k"),
        },
        "cases": cases,
        "by_category": by_category,
        "rag_wins": [c["id"] for c in cases if c["winner"] == "rag"],
        "engine_wins": [c["id"] for c in cases if c["winner"] == "engine"],
        "ties": [c["id"] for c in cases if c["winner"] == "tie"],
    }
