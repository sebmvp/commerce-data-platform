"""Thin grounded LLM path over ContextBundle.

Fake provider is the default (tests, no keys). A real provider is only
used when CDP_LLM_API_KEY is set. The model never sees the whole business
and never writes.
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol

from ..context import assemble_context
from ..context.model import ContextBundle


class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


class FakeProvider:
    name = "fake"

    def complete(self, prompt: str) -> str:
        if "SUFFICIENT: false" in prompt or "SUFFICIENT: False" in prompt:
            return (
                "ABSTAIN: required context is missing. "
                "Do not invent a listing, price, or market."
            )
        sku = ""
        for token in prompt.split():
            if "-" in token and any(ch.isdigit() for ch in token):
                sku = token.strip(".,")
                break
        return (
            f"Grounded on the assembled ContextBundle"
            + (f" for {sku}" if sku else "")
            + ". Use the cited objects, metrics, and history; "
            "do not add facts that are not in the bundle."
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
                            "If SUFFICIENT is false, abstain."
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
            {"type": o.get("type"), "id": o.get("id")}
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
        f"Answer the question using only this ContextBundle.\n"
        f"{json.dumps(compact, default=str)}"
    )


def ground_answer(
    con,
    *,
    question: str,
    intent: str | None = None,
    sku: str | None = None,
    provider: LLMProvider | None = None,
) -> dict[str, Any]:
    bundle = assemble_context(con, question=question, intent=intent, sku=sku)
    used = provider or get_provider()
    if not bundle.sufficient:
        missing = ", ".join(m.concept for m in bundle.missing_context)
        answer = (
            f"ABSTAIN: context is insufficient"
            + (f" (missing {missing})" if missing else "")
            + ". The model is not allowed to invent the missing facts."
        )
        return {
            "answer": answer,
            "abstained": True,
            "provider": used.name,
            "model": getattr(used, "model", used.name),
            "bundle": bundle.to_dict(),
            "evidence": {
                "missing_context": bundle.to_dict().get("missing_context"),
                "provenance": bundle.to_dict().get("provenance"),
            },
        }
    answer = used.complete(_prompt(bundle))
    return {
        "answer": answer,
        "abstained": False,
        "provider": used.name,
        "model": getattr(used, "model", used.name),
        "bundle": bundle.to_dict(),
        "evidence": {
            "objects": [o.ref() for o in bundle.objects],
            "metrics": bundle.metrics,
            "retrieved_evidence": bundle.to_dict().get("retrieved_evidence"),
            "provenance": bundle.to_dict().get("provenance"),
        },
    }
