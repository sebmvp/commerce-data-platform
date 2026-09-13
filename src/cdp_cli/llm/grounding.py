"""Fail-closed grounding over one ContextBundle.

Malformed provider output is INVALID, not trusted prose. Unknown or
missing citations are grounding failures. The model cannot override
an insufficient bundle. Suggested actions must match registered schemas
and must not invent a numeric price.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from ..core.domain import get_active_domain
from ..core.engine import assemble_context
from ..core.model import ContextBundle
from ..core.plan import QuestionPlan
from .gateway import LLMProvider, get_provider, is_real_provider_name
from .planner import plan_question

GroundingStatus = Literal["grounded", "abstained", "invalid"]


class SuggestedActionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    target_type: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = {}
    reason: str | None = None
    recommendation: str | None = None


class GroundedModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    abstained: bool
    evidence_refs: list[str]
    caveats: list[str] = []
    suggested_action: SuggestedActionModel | None = None


def _prompt(bundle: ContextBundle) -> str:
    payload = bundle.to_dict()
    compact = {
        "question": payload.get("question"),
        "intent": payload.get("intent"),
        "sufficient": payload.get("sufficient"),
        "missing_context": payload.get("missing_context"),
        "evidence_catalog": payload.get("evidence_catalog"),
        "evidence_units": [
            {
                "ref": u.get("ref"),
                "kind": u.get("kind"),
                "label": u.get("label"),
                "object_ref": u.get("object_ref"),
                "value": u.get("value"),
            }
            for u in (payload.get("evidence_units") or [])[:40]
        ],
        "objects": [
            {
                "type": o.get("type"),
                "id": o.get("id"),
                "ref": f"{o.get('type')}:{o.get('id')}",
            }
            for o in payload.get("objects") or []
        ],
        "relationships": payload.get("relationships"),
        "facts": payload.get("facts"),
        "metrics": payload.get("metrics"),
        "events": payload.get("events"),
        "applicable_rules": payload.get("applicable_rules"),
        "applicable_policies": payload.get("applicable_policies"),
        "retrieved_evidence": payload.get("retrieved_evidence"),
    }
    flag = "true" if bundle.sufficient else "false"
    return (
        f"SUFFICIENT: {flag}\n"
        "Answer using only this ContextBundle.\n"
        "Return JSON only: answer, abstained, evidence_refs, caveats, "
        "suggested_action. Cite only evidence_catalog ids. No extra fields.\n"
        "Do not invent evidence refs. Do not invent a numeric price.\n"
        f"{json_dumps(compact)}"
    )


def json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, default=str)


def _validate_suggested_action(action: SuggestedActionModel | None) -> str | None:
    if action is None:
        return None
    allowed = get_active_domain().action_types
    if allowed and action.action_type not in allowed:
        return f"unknown action_type {action.action_type!r}"
    if action.target_type and action.target_type not in {"item", "listing"}:
        return f"unknown target_type {action.target_type!r}"
    payload = action.payload or {}
    if action.action_type == "propose_reprice":
        if any(key in payload for key in ("new_price_usd", "price_usd", "markdown")):
            return (
                "numeric price is not allowed without an approved pricing policy"
            )
        rec = (action.recommendation or "").strip().upper()
        if rec and rec not in {"REVIEW_PRICE", "KEEP_PRICE", "INSUFFICIENT_EVIDENCE"}:
            return f"unknown price recommendation {action.recommendation!r}"
    return None


def parse_grounded(raw: str, bundle: ContextBundle) -> dict[str, Any]:
    """Validate model JSON against the exact bundle. Fail closed."""
    import json

    allowed = bundle.citeable_refs()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "reason": "malformed JSON"}
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "model output is not an object"}
    try:
        parsed = GroundedModelOutput.model_validate(payload)
    except ValidationError as exc:
        return {"ok": False, "reason": f"invalid schema: {exc.error_count()} error(s)"}

    refs = list(parsed.evidence_refs)
    invalid = [r for r in refs if r not in allowed]
    if invalid:
        return {
            "ok": False,
            "reason": f"unknown evidence refs: {', '.join(invalid)}",
            "invalid_citations": invalid,
        }
    if not parsed.abstained and not refs:
        return {"ok": False, "reason": "non-abstaining answer cited no evidence"}
    if parsed.abstained is False and not bundle.sufficient:
        return {"ok": False, "reason": "model overrode insufficient context"}

    action_err = _validate_suggested_action(parsed.suggested_action)
    if action_err:
        return {"ok": False, "reason": action_err}

    return {
        "ok": True,
        "answer": parsed.answer,
        "abstained": parsed.abstained,
        "evidence_refs": refs,
        "caveats": list(parsed.caveats),
        "suggested_action": None
        if parsed.suggested_action is None
        else parsed.suggested_action.model_dump(),
    }


def _invalid(
    *,
    reason: str,
    bundle: ContextBundle,
    plan: dict[str, Any],
    provider: LLMProvider,
    raw: str | None = None,
) -> dict[str, Any]:
    return _result(
        answer=f"ABSTAIN: grounding invalid ({reason}).",
        abstained=True,
        grounding_status="invalid",
        evidence_refs=[],
        caveats=[reason],
        suggested_action=None,
        plan=plan,
        provider=provider,
        bundle=bundle,
        invalid_reason=reason,
        untrusted_output=raw,
    )


def _result(
    *,
    answer: str,
    abstained: bool,
    grounding_status: GroundingStatus,
    evidence_refs: list[str],
    caveats: list[str],
    suggested_action: dict[str, Any] | None,
    plan: dict[str, Any],
    provider: LLMProvider,
    bundle: ContextBundle,
    invalid_reason: str | None = None,
    untrusted_output: str | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = bundle.to_dict()
    cited = [u for u in payload.get("evidence_units") or [] if u.get("ref") in set(evidence_refs)]
    out: dict[str, Any] = {
        "question": bundle.question,
        "answer": answer,
        "abstained": abstained,
        "grounding_status": grounding_status,
        "evidence_refs": evidence_refs,
        "cited_evidence": cited,
        "invalid_citations": [],
        "caveats": caveats,
        "suggested_action": suggested_action,
        "plan": plan,
        "tool_trace": tool_trace or [],
        "provider": provider.name,
        "model": getattr(provider, "model", provider.name),
        "provider_kind": "fake" if provider.name == "fake" else "unknown",
        "bundle": payload,
        "evidence": {
            "missing_context": payload.get("missing_context"),
            "provenance": payload.get("provenance"),
            "evidence_refs": evidence_refs,
            "evidence_catalog": payload.get("evidence_catalog"),
            "evidence_units": payload.get("evidence_units"),
        },
        "policies": payload.get("applicable_policies") or [],
        "sufficient": bundle.sufficient,
    }
    if grounding_status == "invalid":
        out["raw_model_output"] = None
        out["invalid_reason"] = invalid_reason
        out["untrusted_output"] = untrusted_output
    return out


def ground_from_bundle(
    bundle: ContextBundle,
    *,
    plan: QuestionPlan | dict[str, Any] | None = None,
    provider: LLMProvider | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    used = provider or get_provider()
    if isinstance(plan, QuestionPlan):
        plan_dict = plan.to_dict()
    else:
        plan_dict = plan or {
            "capability": bundle.intent,
            "subject": None,
            "source": "bundle",
        }
    if not bundle.sufficient:
        missing = ", ".join(m.concept for m in bundle.missing_context)
        return _result(
            answer=(
                "ABSTAIN: context is insufficient"
                + (f" (missing {missing})" if missing else "")
                + ". The model is not allowed to invent the missing facts."
            ),
            abstained=True,
            grounding_status="abstained",
            evidence_refs=[],
            caveats=[f"missing {missing}" if missing else "insufficient context"],
            suggested_action=None,
            plan=plan_dict,
            provider=used,
            bundle=bundle,
            tool_trace=tool_trace,
        )
    try:
        raw = used.complete(_prompt(bundle))
    except Exception as exc:
        return _invalid(
            reason=f"provider failure: {type(exc).__name__}",
            bundle=bundle,
            plan=plan_dict,
            provider=used,
        )
    parsed = parse_grounded(raw, bundle)
    if not parsed.get("ok"):
        return _invalid(
            reason=str(parsed.get("reason") or "invalid grounding"),
            bundle=bundle,
            plan=plan_dict,
            provider=used,
            raw=raw,
        )
    status: GroundingStatus = "abstained" if parsed["abstained"] else "grounded"
    return _result(
        answer=parsed["answer"],
        abstained=parsed["abstained"],
        grounding_status=status,
        evidence_refs=parsed["evidence_refs"],
        caveats=parsed["caveats"],
        suggested_action=parsed["suggested_action"],
        plan=plan_dict,
        provider=used,
        bundle=bundle,
        tool_trace=tool_trace,
    )


def ground_answer(
    con,
    *,
    question: str,
    intent: str | None = None,
    sku: str | None = None,
    as_of: str | None = None,
    provider: LLMProvider | None = None,
    tool_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    used = provider or get_provider()
    plan = plan_question(
        question, intent=intent, subject=sku, as_of=as_of, provider=used
    )
    bundle = assemble_context(
        con, question=question, intent=intent, sku=sku, as_of=as_of, plan=plan
    )
    return ground_from_bundle(
        bundle, plan=plan, provider=used, tool_trace=tool_trace
    )


def uses_llm_planner(provider: LLMProvider | None) -> bool:
    return is_real_provider_name(getattr(provider, "name", None))
