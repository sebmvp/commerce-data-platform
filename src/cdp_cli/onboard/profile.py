"""Deterministic source profiler. No LLM. One explicit file only."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?(Z|[+-]\d{2}:?\d{2})?$"
)
_MAX_DISTINCT = 200
_SAMPLE_VALUES = 5
_MAX_ROWS = 5000


def _as_scalar(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)[:80]
    return value


def _infer_type(values: list[Any]) -> str:
    present = [v for v in values if v is not None and v != ""]
    if not present:
        return "empty"
    kinds = set()
    for value in present[:50]:
        if isinstance(value, bool):
            kinds.add("bool")
        elif isinstance(value, int) and not isinstance(value, bool):
            kinds.add("int")
        elif isinstance(value, float):
            kinds.add("float")
        elif isinstance(value, str):
            text = value.strip()
            if _DATE_RE.match(text):
                kinds.add("datetime")
            else:
                try:
                    int(text)
                    kinds.add("int")
                except ValueError:
                    try:
                        float(text)
                        kinds.add("float")
                    except ValueError:
                        kinds.add("string")
        else:
            kinds.add(type(value).__name__)
    if len(kinds) == 1:
        return kinds.pop()
    if kinds <= {"int", "float"}:
        return "number"
    if "datetime" in kinds and len(kinds) == 1:
        return "datetime"
    return "mixed"


def _is_date_like(values: list[Any]) -> bool:
    present = [v for v in values if v not in (None, "")]
    if not present:
        return False
    hits = 0
    for value in present[:40]:
        text = str(value).strip()
        if _DATE_RE.match(text):
            hits += 1
            continue
        try:
            datetime.fromisoformat(text.removesuffix("Z"))
            hits += 1
        except ValueError:
            continue
    return hits >= max(1, int(0.8 * min(len(present), 40)))


def _load_rows(path: Path) -> tuple[str, list[dict[str, Any]]]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
            if len(rows) >= _MAX_ROWS:
                break
        return "jsonl", rows
    if suffix == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            rows = [r for r in payload if isinstance(r, dict)][:_MAX_ROWS]
            return "json", rows
        if isinstance(payload, dict):
            return "json", [payload]
        raise ValueError("JSON file is not an object or array of objects")
    if suffix == ".csv":
        reader = csv.DictReader(text.splitlines())
        rows = []
        for row in reader:
            rows.append(dict(row))
            if len(rows) >= _MAX_ROWS:
                break
        return "csv", rows
    raise ValueError(f"unsupported source type {suffix or path.name!r}; use jsonl, json, or csv")


def profile_file(path: str | Path) -> dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    if not file_path.is_file():
        raise FileNotFoundError(f"source file not found: {file_path}")
    source_type, rows = _load_rows(file_path)
    truncated = len(rows) >= _MAX_ROWS
    columns: dict[str, list[Any]] = {}
    for row in rows:
        for key, value in row.items():
            columns.setdefault(str(key), []).append(value)
        for key, values in columns.items():
            if key not in row:
                values.append(None)
    fields = []
    candidate_keys = []
    date_fields = []
    n = len(rows)
    for name, values in columns.items():
        while len(values) < n:
            values.append(None)
        nulls = sum(1 for v in values if v is None or v == "")
        present = [_as_scalar(v) for v in values if v not in (None, "")]
        distinct: list[Any] = []
        seen: set[str] = set()
        for value in present:
            marker = repr(value)
            if marker in seen:
                continue
            seen.add(marker)
            distinct.append(value)
            if len(distinct) >= _MAX_DISTINCT:
                break
        inferred = _infer_type(values)
        date_like = inferred == "datetime" or _is_date_like(values)
        if date_like:
            date_fields.append(name)
        unique = n > 0 and nulls == 0 and len(distinct) == n and len(distinct) < _MAX_DISTINCT
        if unique:
            candidate_keys.append(name)
        fields.append(
            {
                "name": name,
                "inferred_type": inferred,
                "null_count": nulls,
                "null_frequency": None if n == 0 else round(nulls / n, 4),
                "distinct_count": len(distinct) if len(distinct) < _MAX_DISTINCT else f">={_MAX_DISTINCT}",
                "date_like": date_like,
                "unique": unique,
                "sample_values": present[:_SAMPLE_VALUES],
            }
        )
    return {
        "path": str(file_path),
        "source_name": file_path.stem,
        "source_type": source_type,
        "row_count": n,
        "truncated": truncated,
        "column_count": len(fields),
        "fields": fields,
        "candidate_natural_keys": candidate_keys,
        "date_like_fields": date_fields,
        "notes": [
            "Deterministic profile. No model involved.",
            "Only the named file was read.",
        ],
    }
