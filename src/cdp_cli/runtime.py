"""Which data environment this process is connected to."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from . import db

KINDS = frozenset({"demo", "heldout", "private"})


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.password:
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        user = parsed.username or ""
        netloc = f"{user}:***@{host}{port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def world_meta(data_dir: Path | None = None) -> dict:
    path = (data_dir or db.data_dir()) / "world.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def world_kind() -> str:
    explicit = (os.environ.get("CDP_WORLD") or "").strip().lower()
    if explicit in KINDS:
        return explicit
    meta = world_meta()
    name = str(meta.get("name") or "").strip().lower()
    if name in KINDS:
        return name
    data = str(db.data_dir())
    if "heldout" in Path(data).name or data.rstrip("/").endswith("sample_data_heldout"):
        return "heldout"
    if data.rstrip("/").endswith(("data/private", "/private")):
        return "private"
    return "demo"


def runtime_info() -> dict:
    meta = world_meta()
    kind = world_kind()
    return {
        "environment": kind,
        "world_name": meta.get("name") or kind,
        "as_of": meta.get("as_of"),
        "purpose": meta.get("purpose"),
        "synthetic": kind != "private",
        "database": _safe_url(db.database_url()),
    }
