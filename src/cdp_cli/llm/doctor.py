"""Local/remote model diagnostics. Never prints secrets. Never downloads models."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from .gateway import load_model_config


def _port_open(host: str, port: int) -> bool:
    sock = socket.socket()
    sock.settimeout(0.4)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def detect_ollama() -> dict[str, Any]:
    reachable = _port_open("127.0.0.1", 11434)
    models: list[str] = []
    error = None
    if reachable:
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/tags", method="GET"
            )
            with urllib.request.urlopen(req, timeout=2) as res:
                payload = json.loads(res.read().decode())
            for item in payload.get("models") or []:
                name = item.get("name") if isinstance(item, dict) else None
                if name:
                    models.append(str(name))
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            error = type(exc).__name__
    return {
        "reachable": reachable,
        "models": models,
        "error": error,
    }


def endpoint_reachable(base_url: str | None, timeout: float = 2.0) -> dict[str, Any]:
    if not base_url:
        return {"ok": False, "detail": "no base URL"}
    parsed = urlparse(base_url)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return {"ok": False, "detail": "unparseable base URL"}
    if not _port_open(host, port):
        return {"ok": False, "detail": f"{host}:{port} closed"}
    models_url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(models_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as res:
            res.read(256)
        return {"ok": True, "detail": "GET /models responded"}
    except urllib.error.HTTPError as exc:
        return {"ok": True, "detail": f"HTTP {exc.code} on GET /models"}
    except (OSError, urllib.error.URLError, TimeoutError):
        return {"ok": False, "detail": f"{host}:{port} open but /models failed"}


def doctor_report() -> dict[str, Any]:
    try:
        config = load_model_config()
        config_error = None
    except ValueError as exc:
        config = None
        config_error = str(exc)
    ollama = detect_ollama()
    info: dict[str, Any] = {
        "provider": None if config is None else config.provider,
        "kind": None if config is None else config.kind,
        "model": None if config is None else config.model,
        "base_url": None if config is None else config.base_url,
        "auth_configured": False if config is None else bool(config.api_key),
        "timeout": None if config is None else config.timeout,
        "capabilities": None if config is None else config.capabilities.to_dict(),
        "config_error": config_error,
        "endpoint_reachable": None,
        "model_callable": False,
        "ollama": ollama,
        "notes": [],
    }
    if config is None:
        info["notes"].append(config_error)
        return info
    if config.provider == "fake":
        info["endpoint_reachable"] = {"ok": True, "detail": "fake provider (no network)"}
        info["model_callable"] = True
        info["notes"].append(
            "Fake/Test provider. Output is extractive, not model reasoning."
        )
        return info
    reach = endpoint_reachable(config.base_url, timeout=min(config.timeout, 3.0))
    info["endpoint_reachable"] = reach
    if not reach["ok"]:
        info["notes"].append(f"endpoint not reachable: {reach['detail']}")
    if config.kind == "remote" and not config.api_key:
        info["notes"].append(
            "remote endpoint has no API key configured "
            "(required for xAI and most hosted APIs; optional for local)"
        )
    if config.kind == "local" and not config.api_key:
        info["notes"].append("local endpoint: API key not required")
    if "x.ai" in (config.base_url or ""):
        info["notes"].append(
            "xAI Chat Completions requires an xAI API key. "
            "A Grok/SuperGrok consumer subscription is not API access."
        )
    if ollama["reachable"] and config.kind == "local":
        if config.model not in ollama["models"] and ollama["models"]:
            info["notes"].append(
                f"Ollama is up but {config.model!r} is not installed. "
                f"Installed: {', '.join(ollama['models'][:8])}. "
                "Will not download a model without explicit approval."
            )
        elif not ollama["models"]:
            info["notes"].append(
                "Ollama is reachable but no models are installed. "
                "Will not download a model without explicit approval."
            )
    return info


def format_doctor(report: dict[str, Any]) -> str:
    lines = [
        "AI runtime",
        f"  provider     {report.get('provider')}",
        f"  kind         {report.get('kind')}",
        f"  model        {report.get('model')}",
        f"  base URL     {report.get('base_url') or '—'}",
        f"  auth         {'configured' if report.get('auth_configured') else 'not set'}",
        f"  timeout      {report.get('timeout')}",
    ]
    caps = report.get("capabilities") or {}
    if caps:
        enabled = [k for k, v in caps.items() if v]
        lines.append(f"  capabilities {' '.join(enabled) or 'none declared'}")
    reach = report.get("endpoint_reachable") or {}
    if reach:
        lines.append(f"  endpoint     {reach.get('detail')}")
    ollama = report.get("ollama") or {}
    if ollama.get("reachable"):
        installed = ", ".join(ollama.get("models") or []) or "(none installed)"
        lines.append(f"  ollama       reachable  models: {installed}")
    else:
        lines.append("  ollama       not running on :11434")
    for note in report.get("notes") or []:
        lines.append(f"  note         {note}")
    return "\n".join(lines) + "\n"


def main() -> int:
    report = doctor_report()
    print(format_doctor(report), end="")
    if report.get("config_error"):
        return 1
    return 0
