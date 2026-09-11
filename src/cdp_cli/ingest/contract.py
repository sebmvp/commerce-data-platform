"""Smallest useful source-adapter contract.

A source adapter turns an external record into validated domain records
plus lineage. It does not write to PostgreSQL. The ingest runner owns
run identity, atomicity, quarantine, and accounting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class SourceLineage:
    source_system: str
    source_record_reference: str
    content_hash: str
    observed_at: datetime | None
    effective_at: datetime | None
    ingest_run_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_system": self.source_system,
            "source_record_reference": self.source_record_reference,
            "content_hash": self.content_hash,
            "observed_at": None if self.observed_at is None else self.observed_at.isoformat(timespec="seconds"),
            "effective_at": None if self.effective_at is None else self.effective_at.isoformat(timespec="seconds"),
            "ingest_run_id": self.ingest_run_id,
        }


@dataclass
class AdaptedRecord:
    """One canonical domain record produced by an adapter."""

    entity_type: str
    natural_key: str
    payload: dict[str, Any]
    lineage: SourceLineage
    reject_reason: str | None = None


@dataclass
class AdaptedBatch:
    source_system: str
    records: list[AdaptedRecord] = field(default_factory=list)
    rejects: list[AdaptedRecord] = field(default_factory=list)

    @property
    def accepted(self) -> list[AdaptedRecord]:
        return [r for r in self.records if not r.reject_reason]


class SourceAdapter(Protocol):
    """Python composition, not a plugin marketplace."""

    source_system: str

    def adapt(self) -> AdaptedBatch: ...
