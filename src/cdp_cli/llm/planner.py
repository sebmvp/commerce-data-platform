"""Question interpretation: deterministic first, optional LLM planner.

The planner may only select registered domain capabilities. It cannot
emit SQL. Invalid model output falls back to deterministic parsing and
records that fallback in the plan notes.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ..clock import iso
from ..core.domain import Domain, get_active_domain
from ..core.plan import QuestionPlan

PLAN_SCHEMA = {
    "type": "object",
    "required": ["capability"],
    "additionalProperties": False,
    "properties": {
        "capability": {"type": "string"},
        "subject": {"type": ["string", "null"]},
        "subject_type": {"type": ["string", "null"]},
        "as_of": {"type": ["string", "null"]},
        "filters": {"type": "object"},
    },
}


class PlannerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str
    subject: str | None = None
    subject_type: str | None = None
    as_of: str | None = None
    filters: dict[str, Any] = {}


def deterministic_plan(
    question: str,
    *,
    intent: str | None = None,
    subject: str | None = None,
    as_of: str | None = None,
    domain: Domain | None = None,
) -> QuestionPlan:
    active = domain or get_active_domain()
    capability = active.resolve_intent(question, intent)
    extracted = active.extract_subject(question, subject)
    as_of_dt = active.extract_as_of(question, as_of)
    return QuestionPlan(
        domain=active.name,
        capability=capability,
        subject=extracted,
        subject_type=active.subject_name if extracted else None,
        as_of=None if as_of_dt is None else iso(as_of_dt),
        source="deterministic",
    )


def _parse_as_of_text(value: str) -> str:
    text = value.strip().removesuffix("Z")
    parsed = datetime.fromisoformat(text)
    return iso(parsed)


def _validate_plan_payload(payload: dict[str, Any], domain: Domain) -> QuestionPlan:
    parsed = PlannerOutput.model_validate(payload)
    capability = parsed.capability.strip()
    if capability not in domain.intents:
        known = ", ".join(sorted(domain.intents))
        raise ValueError(f"unknown capability {capability!r}; known: {known}")
    subject = (parsed.subject or "").strip() or None
    subject_type = (parsed.subject_type or "").strip() or None
    allowed_types = set(domain.entity_types) | {domain.subject_name, "Item", "sku"}
    if subject_type and domain.entity_types and subject_type not in allowed_types:
        raise ValueError(f"unknown object type {subject_type!r}")
    as_of = parsed.as_of.strip() if parsed.as_of else None
    if as_of:
        try:
            as_of = _parse_as_of_text(as_of)
        except ValueError as exc:
            raise ValueError(f"invalid as_of {as_of!r}") from exc
    if parsed.filters:
        raise ValueError("unknown filters; capabilities do not accept free-form filters")
    return QuestionPlan(
        domain=domain.name,
        capability=capability,
        subject=subject,
        subject_type=subject_type or (domain.subject_name if subject else None),
        as_of=as_of,
        filters={},
        source="llm",
    )


def plan_question(
    question: str,
    *,
    intent: str | None = None,
    subject: str | None = None,
    as_of: str | None = None,
    domain: Domain | None = None,
    provider: Any | None = None,
) -> QuestionPlan:
    """Interpret a question into a registered capability.

    Policy: when a real provider is configured, try structured output.
    Invalid schema / unknown capability / unknown object type →
    deterministic fallback (never guessed SQL, never silent execute).
    """
    from . import get_provider

    active = domain or get_active_domain()
    used = provider or get_provider()
    if intent:
        return deterministic_plan(
            question, intent=intent, subject=subject, as_of=as_of, domain=active
        )
    if getattr(used, "name", "fake") not in {"env", "openai"}:
        return deterministic_plan(
            question, intent=intent, subject=subject, as_of=as_of, domain=active
        )
    prompt = (
        "Map the operator question to one registered capability. "
        "Return JSON only.\n"
        f"capabilities: {sorted(active.intents)}\n"
        f"entity_types: {list(active.entity_types)}\n"
        f"subject_name: {active.subject_name}\n"
        f"question: {question}\n"
        f"schema: {json.dumps(PLAN_SCHEMA)}"
    )
    try:
        raw = used.complete(prompt)
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("planner output is not an object")
        return _validate_plan_payload(payload, active)
    except (ValueError, json.JSONDecodeError, TypeError, KeyError, ValidationError) as exc:
        fallback = deterministic_plan(
            question, intent=intent, subject=subject, as_of=as_of, domain=active
        )
        return QuestionPlan(
            domain=fallback.domain,
            capability=fallback.capability,
            subject=fallback.subject,
            subject_type=fallback.subject_type,
            as_of=fallback.as_of,
            filters=fallback.filters,
            source="deterministic_fallback",
            notes=(f"llm planner failed: {exc}",),
        )
