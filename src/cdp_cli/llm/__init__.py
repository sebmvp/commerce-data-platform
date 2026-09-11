"""Grounded LLM path over ContextBundle.

Fake provider is the default (tests, no keys). A real provider is only
used when CDP_LLM_API_KEY is set. The model never sees the whole business,
never writes, and never emits SQL.
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol

from ..core.engine import assemble_context
from ..core.model import ContextBundle
from .planner import deterministic_plan, plan_question


class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


class FakeProvider:
    name = "fake"

    def complete(self, prompt: str) -> str:
        if "\"task\": \"plan\"" in prompt or "capabilities:" in prompt:
            return json.dumps({"capability": "item_state", "subject": None})
        if "SUFFICIENT: false" in prompt or "SUFFICIENT: False" in prompt:
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
        sku = ""
        for token in prompt.split():
            if "-" in token and any(ch.isdigit() for ch in token):
                sku = token.strip(".,")
                break
        return json.dumps(
            {
                "answer": (
                    "Grounded on the assembled ContextBundle"
                    + (f" for {sku}" if sku else "")
                    + ". Use the cited objects, metrics, and history; "
                    "do not add facts that are not in the bundle."
                ),
                "abstained": False,
                "evidence_refs": [],
                "caveats": [],
                "suggested_action": None,
            }
        )


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
                            "Cite only object refs that appear in the bundle."
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
        "Answer the question using only this ContextBundle.\n"
        "Return JSON: {answer, abstained, evidence_refs, caveats, suggested_action}.\n"
        f"{json.dumps(compact, default=str)}"
    )


def _bundle_refs(bundle: ContextBundle) -> set[str]:
    refs = {o.ref() for o in bundle.objects}
    for link in bundle.relationships:
        refs.add(link.from_ref)
        refs.add(link.to_ref)
    return refs


def _parse_grounded(raw: str, bundle: ContextBundle) -> dict[str, Any]:
    allowed = _bundle_refs(bundle)
    parsed: dict[str, Any]
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise TypeError("not an object")
        parsed = payload
    except (json.JSONDecodeError, ValueError, TypeError):
        parsed = {
            "answer": raw,
            "abstained": False,
            "evidence_refs": [],
            "caveats": [],
            "suggested_action": None,
        }
    refs = parsed.get("evidence_refs") or []
    if not isinstance(refs, list):
        refs = []
    refs = [str(r) for r in refs]
    invalid = [r for r in refs if r not in allowed]
    valid = [r for r in refs if r in allowed]
    if not valid:
        valid = sorted(allowed)
    answer = str(parsed.get("answer") or raw)
    abstained = bool(parsed.get("abstained"))
    caveats = parsed.get("caveats") or []
    if not isinstance(caveats, list):
        caveats = [str(caveats)]
    if invalid:
        caveats = list(caveats) + [f"dropped invalid citations: {', '.join(invalid)}"]
    return {
        "answer": answer,
        "abstained": abstained,
        "evidence_refs": valid,
        "invalid_citations": invalid,
        "caveats": [str(c) for c in caveats],
        "suggested_action": parsed.get("suggested_action"),
    }


def ground_answer(
    con,
    *,
    question: str,
    intent: str | None = None,
    sku: str | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    used = provider or get_provider()
    plan = plan_question(
        question, intent=intent, subject=sku, provider=used
    )
    bundle = assemble_context(
        con, question=question, intent=intent, sku=sku, plan=plan
    )
    if not bundle.sufficient:
        missing = ", ".join(m.concept for m in bundle.missing_context)
        answer = (
            "ABSTAIN: context is insufficient"
            + (f" (missing {missing})" if missing else "")
            + ". The model is not allowed to invent the missing facts."
        )
        return {
            "answer": answer,
            "abstained": True,
            "evidence_refs": [],
            "invalid_citations": [],
            "caveats": [f"missing {missing}" if missing else "insufficient context"],
            "suggested_action": None,
            "plan": plan.to_dict(),
            "provider": used.name,
            "model": getattr(used, "model", used.name),
            "bundle": bundle.to_dict(),
            "evidence": {
                "missing_context": bundle.to_dict().get("missing_context"),
                "provenance": bundle.to_dict().get("provenance"),
            },
        }
    grounded = _parse_grounded(used.complete(_prompt(bundle)), bundle)
    return {
        "answer": grounded["answer"],
        "abstained": grounded["abstained"],
        "evidence_refs": grounded["evidence_refs"],
        "invalid_citations": grounded["invalid_citations"],
        "caveats": grounded["caveats"],
        "suggested_action": grounded["suggested_action"],
        "plan": plan.to_dict(),
        "provider": used.name,
        "model": getattr(used, "model", used.name),
        "bundle": bundle.to_dict(),
        "evidence": {
            "objects": [o.ref() for o in bundle.objects],
            "metrics": bundle.metrics,
            "retrieved_evidence": bundle.to_dict().get("retrieved_evidence"),
            "provenance": bundle.to_dict().get("provenance"),
            "evidence_refs": grounded["evidence_refs"],
        },
    }


__all__ = [
    "EnvProvider",
    "FakeProvider",
    "LLMProvider",
    "deterministic_plan",
    "get_provider",
    "ground_answer",
    "plan_question",
]
