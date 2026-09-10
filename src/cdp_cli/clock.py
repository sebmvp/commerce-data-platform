"""Controlled reference clock for demo and evaluation worlds.

Listing ages, inventory ages, and relative phrases such as
"two weeks ago" must resolve against a frozen world timestamp so the
same repository produces the same historical result next month.

Resolution order:
  1. CDP_AS_OF=now|wall  → wall clock (explicit real-time)
  2. CDP_AS_OF=<ISO-8601> → that instant
  3. <data_dir>/world.json as_of → synthetic world clock
  4. wall clock
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_iso(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        raise ValueError("empty timestamp")
    if text.endswith("Z"):
        text = text[:-1]
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def wall_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def world_meta(data_dir: Path | None = None) -> dict[str, Any] | None:
    from . import db

    path = Path(data_dir or db.data_dir()) / "world.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def reference_now(data_dir: Path | None = None) -> datetime:
    env = (os.environ.get("CDP_AS_OF") or "").strip()
    if env.lower() in {"now", "wall"}:
        return wall_now()
    if env:
        return parse_iso(env)
    meta = world_meta(data_dir)
    if meta and meta.get("as_of"):
        return parse_iso(str(meta["as_of"]))
    return wall_now()


def iso(dt: datetime | None = None) -> str:
    value = dt or reference_now()
    return value.isoformat(timespec="seconds") + "Z"
