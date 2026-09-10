"""Domain-neutral operational-context types.

These types are the platform core. A business vertical supplies objects,
relationships, facts, metrics, rules, and evidence; it does not replace
this bundle shape.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class EntityRef:
    type: str
    id: str

    def __str__(self) -> str:
        return f"{self.type}:{self.id}"


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


@dataclass(frozen=True)
class ContextRequirement:
    concept: str
    intent: str
    reason: str = ""


@dataclass
class SufficiencyResult:
    sufficient: bool
    missing: list[MissingContext]
    why: str
    required: tuple[str, ...] = ()


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
    requirements: list[dict[str, Any]] = field(default_factory=list)

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
            "requirements": self.requirements,
        }
