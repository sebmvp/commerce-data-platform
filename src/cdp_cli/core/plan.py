"""Typed question plan. The model may fill this; it may not emit SQL."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class QuestionPlan:
    """Registered capability + subject. Not a free-form query."""

    domain: str
    capability: str
    subject: str | None = None
    subject_type: str | None = None
    as_of: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    source: str = "deterministic"
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
