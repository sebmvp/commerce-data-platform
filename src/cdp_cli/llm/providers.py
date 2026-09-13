"""Model providers. Fake is deterministic. OpenAI-compatible is generic.

Do not add vendor classes when base URL / model / auth already suffice.
A Grok consumer subscription is not an API key.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..core.model import ContextBundle
from .gateway import ModelConfig

_MAX_STRUCTURED_ATTEMPTS = 2


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
    model = "fake"

    def complete(self, prompt: str) -> str:
        if "registered_tools:" in prompt:
            return json.dumps({"action": "finish", "tools": []})
        if "capabilities:" in prompt and "schema:" in prompt:
            return json.dumps({"capability": "unsupported", "subject": None})
        first = prompt.splitlines()[0] if prompt else ""
        if first.upper().startswith("SUFFICIENT: FALSE"):
            return json.dumps(
                {
                    "answer": "ABSTAIN: required context is missing.",
                    "abstained": True,
                    "evidence_refs": [],
                    "caveats": ["required evidence is missing"],
                    "suggested_action": None,
                }
            )
        return json.dumps(_extractive_output(_bundle_payload_from_prompt(prompt)))


class ScriptedProvider:
    """Test double. complete() returns a fixed string or raises."""

    name = "scripted"
    model = "scripted"

    def __init__(self, output: str | Exception) -> None:
        self._output = output

    def complete(self, prompt: str) -> str:
        del prompt
        if isinstance(self._output, Exception):
            raise self._output
        return self._output


class OpenAICompatibleProvider:
    """Generic Chat Completions client. Key optional for local endpoints."""

    name = "openai_compatible"

    def __init__(self, config: ModelConfig | None = None) -> None:
        from .gateway import load_model_config

        self.config = config or load_model_config()
        self.model = self.config.model
        self.base_url = (self.config.base_url or "").rstrip("/")
        self.api_key = self.config.api_key
        self.timeout = self.config.timeout

    def complete(self, prompt: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "Follow the user instructions exactly. "
                    "When JSON is requested, return a JSON object only."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        return self._chat(messages, json_mode=self.config.capabilities.json_mode)

    def _chat(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool,
        json_schema: dict[str, Any] | None = None,
    ) -> str:
        if not self.base_url:
            raise RuntimeError("CDP_MODEL_BASE_URL is not configured")
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if self.config.max_tokens is not None:
            body["max_tokens"] = self.config.max_tokens
        if json_schema and self.config.capabilities.structured_output:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "cdp_output",
                    "schema": json_schema,
                    "strict": True,
                },
            }
        elif json_mode:
            body["response_format"] = {"type": "json_object"}
        last_error: Exception | None = None
        for attempt in range(_MAX_STRUCTURED_ATTEMPTS):
            try:
                return self._post(body)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if (
                    attempt == 0
                    and exc.code == 400
                    and "response_format" in body
                ):
                    body = dict(body)
                    body.pop("response_format", None)
                    continue
                raise _safe_http_error(exc) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"provider unreachable: {type(exc.reason).__name__}") from exc
        raise RuntimeError(f"provider failure: {type(last_error).__name__}")

    def _post(self, body: dict[str, Any]) -> str:
        encoded = json.dumps(body).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=encoded,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                payload = json.loads(res.read().decode())
        except TimeoutError as exc:
            raise RuntimeError("provider timeout") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("malformed provider response") from exc
        if not isinstance(content, str):
            raise TypeError("malformed provider response")
        return content


def _safe_http_error(exc: urllib.error.HTTPError) -> RuntimeError:
    return RuntimeError(f"provider HTTP {exc.code}")


def extractive_from_bundle(bundle: ContextBundle) -> dict[str, Any]:
    return _extractive_output(bundle.to_dict())
