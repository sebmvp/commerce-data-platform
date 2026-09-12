"""Grounded LLM path over ContextBundle.

Fake provider is the default (tests, no keys). A real provider is only
used when CDP_LLM_API_KEY is set. The model never sees the whole business,
never writes, and never emits SQL.

Grounding fails closed: malformed output, missing citations, unknown refs,
or invalid suggested actions are not trusted answers.
"""
from __future__ import annotations

import json
import os
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from ..core.domain import get_active_domain
from ..core.engine import assemble_context
from ..core.model import ContextBundle
from .planner import deterministic_plan, plan_question

GroundingStatus = Literal["grounded", "abstained", "invalid"]


class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


class SuggestedActionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    target_type: str | None = None
    target_id: str | None = None
    payload: dict[str, Any] = {}
    reason: str | None = None


class GroundedModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    abstained: bool
    evidence_refs: list[str]
    caveats: list[str] = []
    suggested_action: SuggestedActionModel | None = None


def _bundle_payload_from_prompt(prompt: str) -> dict[str, Any] | None:
    marker = "Answer using only this ContextBundle."
    blob = prompt[prompt.index(marker) :] if marker in prompt else prompt
    start = blob.find("{")
    if start < 0:
        return None
    try:
        payload = json.loads(blob[start:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _scalar_lines(mapping: dict[str, Any] | None, kind: str, *, limit: int = 12) -> list[str]:
    lines: list[str] = []

    def consider(key: str, value: Any) -> None:
        if len(lines) >= limit:
            return
        if "margin" in key.lower():
            return
        if isinstance(value, bool):
            lines.append(f"{kind} {key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)) or (isinstance(value, str) and value.strip()):
            lines.append(f"{kind} {key}: {value}")
        elif isinstance(value, dict):
            for nested_key, nested in value.items():
                consider(f"{key}.{nested_key}", nested)
                if len(lines) >= limit:
                    return

    for raw_key, raw_value in (mapping or {}).items():
        consider(str(raw_key), raw_value)
        if len(lines) >= limit:
            break
    return lines


def _select_refs(payload: dict[str, Any]) -> list[str]:
    catalog = [str(item) for item in payload.get("evidence_catalog") or []]
    allowed = set(catalog)
    chosen: list[str] = []

    def take(ref: str) -> None:
        if ref in allowed and ref not in chosen:
            chosen.append(ref)

    seen_types: set[str] = set()
    for obj in payload.get("objects") or []:
        if not isinstance(obj, dict):
            continue
        typ = str(obj.get("type") or "")
        ident = str(obj.get("id") or "")
        if typ and ident and typ not in seen_types:
            take(f"object:{typ}:{ident}")
            seen_types.add(typ)
    for ref in catalog:
        if ref.startswith(("fact:", "metric:")):
            take(ref)
    for prefix in ("rule:", "note:", "event:"):
        for ref in catalog:
            if ref.startswith(prefix):
                take(ref)
    for ref in catalog:
        if ref.startswith("object:"):
            take(ref)
        if len(chosen) >= 12:
            break
    return chosen[:12]


def _extractive_output(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {
            "answer": "ABSTAIN: the fake provider could not read the ContextBundle.",
            "abstained": True,
            "evidence_refs": [],
            "caveats": ["bundle payload missing from prompt"],
            "suggested_action": None,
        }
    refs = _select_refs(payload)
    if not refs:
        return {
            "answer": "ABSTAIN: the ContextBundle published no citeable evidence.",
            "abstained": True,
            "evidence_refs": [],
            "caveats": ["empty evidence_catalog"],
            "suggested_action": None,
        }
    lines = [
        "Extracted from the ContextBundle (fake provider; not a model).",
    ]
    intent = payload.get("intent")
    if intent:
        lines.append(f"intent: {intent}")
    lines.extend(_scalar_lines(payload.get("facts"), "fact"))
    lines.extend(_scalar_lines(payload.get("metrics"), "metric"))
    object_bits = []
    for obj in payload.get("objects") or []:
        if isinstance(obj, dict) and obj.get("type") and obj.get("id"):
            object_bits.append(f"{obj['type']}:{obj['id']}")
        if len(object_bits) >= 8:
            break
    if object_bits:
        lines.append("objects: " + "; ".join(object_bits))
    notes = payload.get("retrieved_evidence") or []
    note_titles = []
    for note in notes:
        if isinstance(note, dict):
            title = note.get("title") or note.get("note_id")
            if title:
                note_titles.append(str(title))
        if len(note_titles) >= 3:
            break
    if note_titles:
        lines.append("notes: " + "; ".join(note_titles))
    return {
        "answer": "\n".join(lines),
        "abstained": False,
        "evidence_refs": refs,
        "caveats": [],
        "suggested_action": None,
    }


class FakeProvider:
    """Deterministic extractive provider. Restates bundle values; invents none."""

    name = "fake"

    def complete(self, prompt: str) -> str:
        if "capabilities:" in prompt and "schema:" in prompt:
            return json.dumps({"capability": "item_state", "subject": None})
        first = prompt.splitlines()[0] if prompt else ""
        if first.upper().startswith("SUFFICIENT: FALSE"):
            return json.dumps(
                {
                    "answer": (
                        "ABSTAIN: required context is missing. "
                        "Do not invent a listing, price, or market."
                    ),
                    "abstained": True,
                    "evidence_refs": [],
                    "caveats": ["required evidence is missing"],
                    "suggested_action": None,
                }
            )
        return json.dumps(_extractive_output(_bundle_payload_from_prompt(prompt)))


class EnvProvider:
    """OpenAI-compatible chat completions. No keys in code or logs."""

    name = "env"

    def __init__(self) -> None:
        self.api_key = os.environ.get("CDP_LLM_API_KEY", "")
        self.base_url = os.environ.get(
            "CDP_LLM_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self.model = os.environ.get("CDP_LLM_MODEL", "gpt-4o-mini")

    def complete(self, prompt: str) -> str:
        import json as _json
        import urllib.request

        body = _json.dumps(
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Answer only from the ContextBundle. "
                            "If SUFFICIENT is false, abstain. "
                            "Return JSON with answer, abstained, "
                            "evidence_refs, caveats, suggested_action. "
                            "Cite only evidence_catalog entries. "
                            "Do not invent refs. extra fields are forbidden."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            }
        ).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as res:
            payload = _json.loads(res.read().decode())
        return payload["choices"][0]["message"]["content"]


class ScriptedProvider:
    """Test double. complete() returns a fixed string or raises."""

    name = "scripted"

    def __init__(self, output: str | Exception) -> None:
        self._output = output

    def complete(self, prompt: str) -> str:
        del prompt
        if isinstance(self._output, Exception):
            raise self._output
        return self._output


def get_provider(name: str | None = None) -> LLMProvider:
    chosen = (name or os.environ.get("CDP_LLM_PROVIDER") or "fake").lower()
    if chosen in {"env", "openai"} and os.environ.get("CDP_LLM_API_KEY"):
        return EnvProvider()
    return FakeProvider()


def _prompt(bundle: ContextBundle) -> str:
    payload = bundle.to_dict()
    compact = {
        "question": payload.get("question"),
        "intent": payload.get("intent"),
        "sufficient": payload.get("sufficient"),
        "missing_context": payload.get("missing_context"),
        "evidence_catalog": payload.get("evidence_catalog"),
        "objects": [
            {"type": o.get("type"), "id": o.get("id"), "ref": f"{o.get('type')}:{o.get('id')}"}
            for o in payload.get("objects") or []
        ],
        "relationships": payload.get("relationships"),
        "facts": payload.get("facts"),
        "metrics": payload.get("metrics"),
        "events": payload.get("events"),
        "applicable_rules": payload.get("applicable_rules"),
        "retrieved_evidence": payload.get("retrieved_evidence"),
    }
    flag = "true" if bundle.sufficient else "false"
    return (
        f"SUFFICIENT: {flag}\n"
        "Answer using only this ContextBundle.\n"
        "Return JSON only: answer, abstained, evidence_refs, caveats, "
        "suggested_action. Cite only evidence_catalog ids. No extra fields.\n"
        f"{json.dumps(compact, default=str)}"
    )


def _invalid(
    *,
    reason: str,
    bundle: ContextBundle,
    plan: dict[str, Any],
    provider: LLMProvider,
    raw: str | None = None,
) -> dict[str, Any]:
    return {
        "answer": f"ABSTAIN: grounding invalid ({reason}).",
        "abstained": True,
        "grounding_status": "invalid",
        "evidence_refs": [],
        "invalid_citations": [],
        "caveats": [reason],
        "suggested_action": None,
        "plan": plan,
        "provider": provider.name,
        "model": getattr(provider, "model", provider.name),
        "bundle": bundle.to_dict(),
        "evidence": {
            "missing_context": bundle.to_dict().get("missing_context"),
            "provenance": bundle.to_dict().get("provenance"),
        },
        "raw_model_output": None,
        "invalid_reason": reason,
        "untrusted_output": raw,
    }


def _validate_suggested_action(action: SuggestedActionModel | None) -> str | None:
    if action is None:
        return None
    allowed = get_active_domain().action_types
    if allowed and action.action_type not in allowed:
        return f"unknown action_type {action.action_type!r}"
    if action.target_type and action.target_type not in {"item", "listing"}:
        return f"unknown target_type {action.target_type!r}"
    if action.action_type == "propose_reprice":
        price = (action.payload or {}).get("new_price_usd")
        if price is not None:
            try:
                if float(price) <= 0:
                    return "new_price_usd must be positive"
            except (TypeError, ValueError):
                return "new_price_usd must be numeric"
    return None


def parse_grounded(raw: str, bundle: ContextBundle) -> dict[str, Any]:
    """Validate model JSON against the exact bundle. Fail closed."""
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


def ground_answer(
    con,
    *,
    question: str,
    intent: str | None = None,
    sku: str | None = None,
    as_of: str | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    used = provider or get_provider()
    plan = plan_question(
        question, intent=intent, subject=sku, as_of=as_of, provider=used
    )
    bundle = assemble_context(
        con, question=question, intent=intent, sku=sku, as_of=as_of, plan=plan
    )
    plan_dict = plan.to_dict()
    if not bundle.sufficient:
        missing = ", ".join(m.concept for m in bundle.missing_context)
        return {
            "answer": (
                "ABSTAIN: context is insufficient"
                + (f" (missing {missing})" if missing else "")
                + ". The model is not allowed to invent the missing facts."
            ),
            "abstained": True,
            "grounding_status": "abstained",
            "evidence_refs": [],
            "invalid_citations": [],
            "caveats": [f"missing {missing}" if missing else "insufficient context"],
            "suggested_action": None,
            "plan": plan_dict,
            "provider": used.name,
            "model": getattr(used, "model", used.name),
            "bundle": bundle.to_dict(),
            "evidence": {
                "missing_context": bundle.to_dict().get("missing_context"),
                "provenance": bundle.to_dict().get("provenance"),
            },
        }
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
    return {
        "answer": parsed["answer"],
        "abstained": parsed["abstained"],
        "grounding_status": "abstained" if parsed["abstained"] else "grounded",
        "evidence_refs": parsed["evidence_refs"],
        "invalid_citations": [],
        "caveats": parsed["caveats"],
        "suggested_action": parsed["suggested_action"],
        "plan": plan_dict,
        "provider": used.name,
        "model": getattr(used, "model", used.name),
        "bundle": bundle.to_dict(),
        "evidence": {
            "objects": [o.ref() for o in bundle.objects],
            "metrics": bundle.metrics,
            "retrieved_evidence": bundle.to_dict().get("retrieved_evidence"),
            "provenance": bundle.to_dict().get("provenance"),
            "evidence_refs": parsed["evidence_refs"],
            "evidence_catalog": bundle.to_dict().get("evidence_catalog"),
        },
    }


__all__ = [
    "EnvProvider",
    "FakeProvider",
    "GroundedModelOutput",
    "LLMProvider",
    "ScriptedProvider",
    "deterministic_plan",
    "get_provider",
    "ground_answer",
    "parse_grounded",
    "plan_question",
]
