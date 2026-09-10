"""Generic ContextBundle assembly.

The domain supplies intent resolution and typed evidence. This module
packages that evidence, computes rule-based sufficiency, and never
interprets vertical vocabulary (channels, listings, costs, …).
"""
from __future__ import annotations

from typing import Any

from ..clock import iso, reference_now
from .domain import Domain, get_active_domain
from .model import ContextBundle, MissingContext, SufficiencyResult


def evaluate_sufficiency(
    *,
    intent: str,
    required: tuple[str, ...],
    missing: list[MissingContext],
) -> SufficiencyResult:
    sufficient = not missing
    needed = ", ".join(required)
    if sufficient:
        why = f"{intent} requires {needed}. All of that evidence is present."
    else:
        miss = ", ".join(m.concept for m in missing)
        why = f"{intent} requires {needed}. Missing: {miss}."
    return SufficiencyResult(
        sufficient=sufficient,
        missing=missing,
        why=why,
        required=required,
    )


def assemble_context(
    con: Any,
    *,
    question: str,
    intent: str | None = None,
    subject: str | None = None,
    sku: str | None = None,
    as_of: str | None = None,
    domain: Domain | None = None,
) -> ContextBundle:
    """Build a typed context bundle for a bounded operational question.

    `sku` is accepted as a compatibility alias for `subject`.
    """
    active = domain or get_active_domain()
    resolved = active.resolve_intent(question, intent)
    target = active.extract_subject(question, subject or sku)
    as_of_dt = active.extract_as_of(question, as_of)
    as_of_iso = iso(as_of_dt or reference_now())

    assembled = active.assemble(
        con,
        intent=resolved,
        question=question,
        subject=target,
        as_of_dt=as_of_dt,
    )
    missing = list(assembled.get("missing") or [])
    required = active.required_concepts.get(resolved, ())
    sufficiency = evaluate_sufficiency(
        intent=resolved, required=required, missing=missing
    )

    notes = [
        "FACT/DERIVED values come from typed business tools, not prompt memory.",
        "sufficient is rule-based: every required concept is present or listed in missing_context.",
        "Ages and relative dates use the world clock when world.json is present.",
    ]
    if not sufficiency.sufficient:
        notes.append(
            "Required context is incomplete — a copilot should abstain or qualify."
        )

    missing_names = {m.concept for m in sufficiency.missing}
    requirements = [
        {"concept": concept, "present": concept not in missing_names}
        for concept in required
    ]

    return ContextBundle(
        question=question,
        intent=resolved,
        as_of=as_of_iso,
        objects=assembled.get("objects") or [],
        relationships=assembled.get("links") or [],
        facts=assembled.get("facts") or {},
        metrics=assembled.get("metrics") or {},
        events=assembled.get("events") or [],
        applicable_rules=assembled.get("rules") or [],
        retrieved_evidence=assembled.get("retrieved_evidence") or [],
        provenance={
            "tool": "assemble_context",
            "domain": active.name,
            "as_of": as_of_iso,
            "source_tools": assembled.get("source_tools", []),
            "source_relations": assembled.get("source_relations", []),
            "metric_names": sorted(assembled.get("metrics") or {}),
            "notes": notes,
        },
        missing_context=sufficiency.missing,
        sufficient=sufficiency.sufficient,
        why=sufficiency.why,
        requirements=requirements,
    )
