"""Canonical operational-context types.

The LLM and operator should see objects, links, events, and actions —
not warehouse tables. These types are store-agnostic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ContextObject:
    type: str
    id: str
    properties: dict[str, Any]

    def ref(self) -> str:
        return f"{self.type}:{self.id}"


@dataclass
class ContextLink:
    type: str
    from_ref: str
    to_ref: str


@dataclass
class ContextEvent:
    type: str
    at: str | None
    object_ref: str
    source: str
    detail: Any = None


@dataclass
class MissingContext:
    concept: str
    reason: str
    required_for: str


@dataclass
class ContextBundle:
    """Sufficient, traceable operational context for one question."""

    question: str
    intent: str
    as_of: str
    objects: list[ContextObject] = field(default_factory=list)
    relationships: list[ContextLink] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    events: list[ContextEvent] = field(default_factory=list)
    applicable_rules: list[dict[str, Any]] = field(default_factory=list)
    retrieved_evidence: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    missing_context: list[MissingContext] = field(default_factory=list)
    sufficient: bool = False
    why: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "intent": self.intent,
            "as_of": self.as_of,
            "objects": [asdict(o) for o in self.objects],
            "relationships": [asdict(r) for r in self.relationships],
            "facts": self.facts,
            "metrics": self.metrics,
            "events": [asdict(e) for e in self.events],
            "applicable_rules": self.applicable_rules,
            "retrieved_evidence": self.retrieved_evidence,
            "provenance": self.provenance,
            "missing_context": [asdict(m) for m in self.missing_context],
            "sufficient": self.sufficient,
            "why": self.why,
        }
