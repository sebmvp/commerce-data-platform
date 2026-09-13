"""Provider-neutral model configuration and gateway.

No framework. One generic OpenAI-compatible Chat Completions transport
covers Ollama, vLLM, xAI, and other compatible endpoints. Fake is the
CI default. API keys are optional for local endpoints and are never logged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

ProviderName = Literal["fake", "openai_compatible"]
ProviderKind = Literal["fake", "local", "remote"]

_REAL_NAMES = frozenset({"openai_compatible", "env", "openai"})
_COMPAT_ALIASES = {
    "env": "openai_compatible",
    "openai": "openai_compatible",
    "ollama": "openai_compatible",
    "vllm": "openai_compatible",
    "xai": "openai_compatible",
}


@dataclass(frozen=True)
class ModelCapabilities:
    structured_output: bool = False
    tool_calling: bool = False
    json_mode: bool = False
    streaming: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "structured_output": self.structured_output,
            "tool_calling": self.tool_calling,
            "json_mode": self.json_mode,
            "streaming": self.streaming,
        }


@dataclass
class ModelConfig:
    provider: str = "fake"
    base_url: str | None = None
    model: str = "fake"
    api_key: str | None = None
    timeout: float = 30.0
    temperature: float = 0.0
    max_tokens: int | None = None
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)

    @property
    def kind(self) -> ProviderKind:
        if self.provider == "fake":
            return "fake"
        host = (urlparse(self.base_url or "").hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return "local"
        return "remote"

    def public_dict(self) -> dict[str, Any]:
        """Operator-visible config. Never includes the API key."""
        return {
            "provider": self.provider,
            "kind": self.kind,
            "model": self.model,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "auth_configured": bool(self.api_key),
            "capabilities": self.capabilities.to_dict(),
            "real": self.provider != "fake",
        }


class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def _flag(*names: str) -> bool:
    raw = _env(*names).lower()
    return raw in {"1", "true", "yes", "on"}


def load_model_config() -> ModelConfig:
    raw = _env("CDP_MODEL_PROVIDER", "CDP_LLM_PROVIDER", default="fake").lower()
    provider = _COMPAT_ALIASES.get(raw, raw) or "fake"
    if provider not in {"fake", "openai_compatible"}:
        raise ValueError(
            f"unknown CDP_MODEL_PROVIDER {raw!r}; "
            "use fake or openai_compatible"
        )
    timeout_raw = _env("CDP_MODEL_TIMEOUT", "CDP_LLM_TIMEOUT", default="30")
    temp_raw = _env("CDP_MODEL_TEMPERATURE", "CDP_LLM_TEMPERATURE", default="0")
    max_raw = _env("CDP_MODEL_MAX_TOKENS", "CDP_LLM_MAX_TOKENS")
    default_url = (
        "http://localhost:11434/v1" if raw == "ollama" else "https://api.openai.com/v1"
    )
    if raw == "xai":
        default_url = "https://api.x.ai/v1"
    base = _env("CDP_MODEL_BASE_URL", "CDP_LLM_BASE_URL", default=default_url)
    model = _env(
        "CDP_MODEL_NAME",
        "CDP_LLM_MODEL",
        default="fake" if provider == "fake" else "gpt-4o-mini",
    )
    key = _env("CDP_MODEL_API_KEY", "CDP_LLM_API_KEY") or None
    caps = ModelCapabilities(
        json_mode=_flag("CDP_MODEL_JSON_MODE"),
        structured_output=_flag("CDP_MODEL_STRUCTURED"),
        tool_calling=_flag("CDP_MODEL_TOOLS"),
        streaming=_flag("CDP_MODEL_STREAMING"),
    )
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise ValueError(f"invalid CDP_MODEL_TIMEOUT {timeout_raw!r}") from exc
    try:
        temperature = float(temp_raw)
    except ValueError as exc:
        raise ValueError(f"invalid CDP_MODEL_TEMPERATURE {temp_raw!r}") from exc
    max_tokens = None
    if max_raw:
        try:
            max_tokens = int(max_raw)
        except ValueError as exc:
            raise ValueError(f"invalid CDP_MODEL_MAX_TOKENS {max_raw!r}") from exc
    if provider == "fake":
        return ModelConfig(
            provider="fake",
            base_url=None,
            model="fake",
            api_key=None,
            timeout=timeout,
            temperature=0.0,
            max_tokens=None,
            capabilities=ModelCapabilities(),
        )
    return ModelConfig(
        provider=provider,
        base_url=base.rstrip("/"),
        model=model,
        api_key=key,
        timeout=timeout,
        temperature=temperature,
        max_tokens=max_tokens,
        capabilities=caps,
    )


def is_real_provider_name(name: str | None) -> bool:
    return (name or "").lower() in _REAL_NAMES


class ModelGateway:
    """Small routing surface over a configured provider."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        config: ModelConfig | None = None,
    ) -> None:
        self.config = config or load_model_config()
        self.provider = provider or get_provider_for_config(self.config)

    @property
    def name(self) -> str:
        return getattr(self.provider, "name", self.config.provider)

    @property
    def model(self) -> str:
        return getattr(self.provider, "model", self.config.model)

    def complete(self, prompt: str) -> str:
        return self.provider.complete(prompt)

    def public_info(self) -> dict[str, Any]:
        info = self.config.public_dict()
        info["provider"] = self.name
        info["model"] = self.model
        return info


def get_provider_for_config(config: ModelConfig) -> LLMProvider:
    from .providers import FakeProvider, OpenAICompatibleProvider

    if config.provider == "fake":
        return FakeProvider()
    return OpenAICompatibleProvider(config)


def get_provider(name: str | None = None) -> LLMProvider:
    """Resolve the process provider. Fake cannot masquerade as a real model."""
    if name:
        chosen = _COMPAT_ALIASES.get(name.lower(), name.lower())
        if chosen == "fake":
            from .providers import FakeProvider

            return FakeProvider()
        if chosen != "openai_compatible":
            raise ValueError(f"unknown provider {name!r}")
        config = load_model_config()
        config.provider = "openai_compatible"
        if config.model == "fake":
            config.model = _env("CDP_MODEL_NAME", "CDP_LLM_MODEL", default="gpt-4o-mini")
        return get_provider_for_config(config)
    return get_provider_for_config(load_model_config())
