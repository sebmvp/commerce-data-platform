"""Shared payload types and query helpers for resale domain services."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal

from cdp_cli.db import Connection

Kind = Literal["fact", "derived", "recommendation"]

# Recommendation policy. Queue rows stay facts; these labels are heuristic.
ACTION_FOR_REASON = {
    "unlisted_owned": "list_next",
    "stale_listing": "review_price_or_channel",
    "high_attention_no_offers": "consider_reprice",
    "listed_active": "monitor",
}


def action_for_reason(reason: str) -> str:
    return ACTION_FOR_REASON.get(reason, "monitor")


def _utcnow() -> datetime:
    from cdp_cli.clock import reference_now

    return reference_now()


def _parse_as_of(as_of: datetime | date | str | None) -> datetime:
    """Accept ISO timestamps (with optional Z) or a date; default now."""
    if as_of is None:
        return _utcnow()
    if isinstance(as_of, datetime):
        if as_of.tzinfo:
            return as_of.astimezone(UTC).replace(tzinfo=None)
        return as_of
    if isinstance(as_of, date):
        return datetime(as_of.year, as_of.month, as_of.day)
    text = str(as_of).strip()
    if not text:
        raise ValueError("as_of is empty")
    text = text.removesuffix("Z")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as e:
        raise ValueError(f"invalid as_of {as_of!r}; expected ISO-8601") from e
    if isinstance(parsed, datetime):
        if parsed.tzinfo:
            return parsed.astimezone(UTC).replace(tzinfo=None)
        return parsed
    return datetime(parsed.year, parsed.month, parsed.day)


@dataclass
class Provenance:
    tool: str
    as_of: str
    source_relations: list[str]
    metric_names: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BusinessPayload:
    kind: Kind
    data: Any
    provenance: Provenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "data": self.data,
            "provenance": self.provenance.to_dict(),
        }


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _records(
    con: Connection, sql: str, params: list | None = None
) -> list[dict[str, Any]]:
    rel = con.execute(sql, params or [])
    cols = [c[0] for c in rel.description]
    out: list[dict[str, Any]] = []
    for row in rel.fetchall():
        rec: dict[str, Any] = {}
        for col, val in zip(cols, row):
            if col in {"payload_json", "raw_json"} and isinstance(val, str):
                try:
                    val = json.loads(val)
                except json.JSONDecodeError:
                    pass
            rec[col] = _jsonable(val)
        out.append(rec)
    return out
