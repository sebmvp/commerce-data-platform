"""OpenAI-compatible ModelGateway transport. No internet."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import pytest

from cdp_cli.llm.gateway import load_model_config
from cdp_cli.llm.providers import FakeProvider, OpenAICompatibleProvider


class _ChatHandler(BaseHTTPRequestHandler):
    require_auth = False
    status = 200
    body: ClassVar[dict] = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }
    last: ClassVar[dict] = {}

    def log_message(self, format: str, *args) -> None:
        del format, args

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode()) if raw else {}
        type(self).last = {
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "model": payload.get("model"),
            "body": payload,
        }
        if self.require_auth and not self.headers.get("Authorization"):
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"no auth"}')
            return
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.status >= 400:
            self.wfile.write(b'{"error":"fail"}')
            return
        self.wfile.write(json.dumps(self.body).encode())


@pytest.fixture()
def chat_server():
    _ChatHandler.require_auth = False
    _ChatHandler.status = 200
    _ChatHandler.body = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }
    _ChatHandler.last = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ChatHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield f"http://{host}:{port}/v1"
    server.shutdown()
    thread.join(timeout=2)


def test_local_endpoint_does_not_require_api_key(chat_server) -> None:
    from cdp_cli.llm.gateway import ModelCapabilities, ModelConfig

    provider = OpenAICompatibleProvider(
        ModelConfig(
            provider="openai_compatible",
            base_url=chat_server,
            model="test-model",
            api_key=None,
            timeout=2.0,
            capabilities=ModelCapabilities(json_mode=False),
        )
    )
    text = provider.complete("hello")
    assert text == '{"ok": true}'
    assert _ChatHandler.last["auth"] is None
    assert _ChatHandler.last["model"] == "test-model"
    assert _ChatHandler.last["path"].endswith("/chat/completions")


def test_bearer_key_is_sent_when_configured(chat_server) -> None:
    from cdp_cli.llm.gateway import ModelCapabilities, ModelConfig

    _ChatHandler.require_auth = True
    provider = OpenAICompatibleProvider(
        ModelConfig(
            provider="openai_compatible",
            base_url=chat_server,
            model="test-model",
            api_key="sk-test",
            timeout=2.0,
            capabilities=ModelCapabilities(json_mode=False),
        )
    )
    text = provider.complete("hello")
    assert text == '{"ok": true}'
    assert _ChatHandler.last["auth"] == "Bearer sk-test"


def test_http_failure_is_safe(chat_server) -> None:
    from cdp_cli.llm.gateway import ModelCapabilities, ModelConfig

    _ChatHandler.status = 500
    provider = OpenAICompatibleProvider(
        ModelConfig(
            provider="openai_compatible",
            base_url=chat_server,
            model="test-model",
            timeout=2.0,
            capabilities=ModelCapabilities(json_mode=False),
        )
    )
    with pytest.raises(RuntimeError, match="HTTP 500"):
        provider.complete("hello")


def test_malformed_provider_response(chat_server) -> None:
    from cdp_cli.llm.gateway import ModelCapabilities, ModelConfig

    _ChatHandler.body = {"choices": [{"message": {}}]}
    provider = OpenAICompatibleProvider(
        ModelConfig(
            provider="openai_compatible",
            base_url=chat_server,
            model="test-model",
            timeout=2.0,
            capabilities=ModelCapabilities(json_mode=False),
        )
    )
    with pytest.raises(RuntimeError, match="malformed"):
        provider.complete("hello")
    _ChatHandler.body = {
        "choices": [{"message": {"content": '{"ok": true}'}}],
    }


def test_timeout(monkeypatch) -> None:
    from cdp_cli.llm.gateway import ModelCapabilities, ModelConfig

    provider = OpenAICompatibleProvider(
        ModelConfig(
            provider="openai_compatible",
            base_url="http://127.0.0.1:1/v1",
            model="x",
            timeout=0.05,
            capabilities=ModelCapabilities(),
        )
    )
    with pytest.raises(RuntimeError):
        provider.complete("hello")


def test_fake_does_not_masquerade_when_key_set(monkeypatch) -> None:
    monkeypatch.setenv("CDP_MODEL_PROVIDER", "fake")
    monkeypatch.setenv("CDP_MODEL_API_KEY", "sk-should-not-matter")
    monkeypatch.setenv("CDP_LLM_API_KEY", "sk-should-not-matter")
    cfg = load_model_config()
    assert cfg.provider == "fake"
    assert cfg.api_key is None
    from cdp_cli.llm.gateway import get_provider

    provider = get_provider()
    assert isinstance(provider, FakeProvider)
    assert provider.name == "fake"


def test_openai_compatible_alias_from_env(monkeypatch) -> None:
    monkeypatch.setenv("CDP_MODEL_PROVIDER", "openai_compatible")
    monkeypatch.setenv("CDP_MODEL_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("CDP_MODEL_NAME", "llama")
    monkeypatch.delenv("CDP_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CDP_LLM_API_KEY", raising=False)
    cfg = load_model_config()
    assert cfg.provider == "openai_compatible"
    assert cfg.kind == "local"
    assert cfg.api_key is None
    assert cfg.model == "llama"
