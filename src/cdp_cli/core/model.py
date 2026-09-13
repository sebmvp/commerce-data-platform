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
class EvidenceUnit:
    """Smallest citeable unit in a ContextBundle. Grounding ids, not PKs."""

    ref: str
    kind: str
    label: str
    value: Any = None
    object_ref: str | None = None
    provenance: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "kind": self.kind,
            "label": self.label,
            "value": self.value,
            "object_ref": self.object_ref,
            "provenance": self.provenance,
        }


def _first_object(objects: list[ContextObject], type_: str) -> ContextObject | None:
    for obj in objects:
        if obj.type == type_:
            return obj
    return None


def _object_for_key(objects: list[ContextObject], key: str) -> ContextObject | None:
    del key
    item = _first_object(objects, "Item")
    if item is not None:
        return item
    return objects[0] if objects else None


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
    applicable_policies: list[dict[str, Any]] = field(default_factory=list)

    def evidence_units(self) -> list[EvidenceUnit]:
        """Typed evidence a model may cite. Never invent extra units."""
        units: list[EvidenceUnit] = []
        seen: set[str] = set()

        def add(unit: EvidenceUnit) -> None:
            if unit.ref in seen:
                return
            seen.add(unit.ref)
            units.append(unit)

        for obj in self.objects:
            add(
                EvidenceUnit(
                    ref=f"object:{obj.ref()}",
                    kind="object",
                    label=f"{obj.type} {obj.id}",
                    value={"type": obj.type, "id": obj.id},
                    object_ref=obj.ref(),
                    provenance="bundle.objects",
                )
            )
        for key, value in self.facts.items():
            obj = _object_for_key(self.objects, key)
            object_id = None if obj is None else obj.id
            specific = None if object_id is None else f"fact:{object_id}:{key}"
            add(
                EvidenceUnit(
                    ref=specific or f"fact:{key}",
                    kind="fact",
                    label=str(key),
                    value=value if not isinstance(value, (dict, list)) else None,
                    object_ref=None if obj is None else obj.ref(),
                    provenance="bundle.facts",
                )
            )
            add(
                EvidenceUnit(
                    ref=f"fact:{key}",
                    kind="fact",
                    label=str(key),
                    value=value if not isinstance(value, (dict, list)) else None,
                    object_ref=None if obj is None else obj.ref(),
                    provenance="bundle.facts",
                )
            )
        for key, value in self.metrics.items():
            obj = _object_for_key(self.objects, key)
            object_id = None if obj is None else obj.id
            specific = None if object_id is None else f"metric:{object_id}:{key}"
            add(
                EvidenceUnit(
                    ref=specific or f"metric:{key}",
                    kind="metric",
                    label=str(key),
                    value=value,
                    object_ref=None if obj is None else obj.ref(),
                    provenance="bundle.metrics",
                )
            )
            add(
                EvidenceUnit(
                    ref=f"metric:{key}",
                    kind="metric",
                    label=str(key),
                    value=value,
                    object_ref=None if obj is None else obj.ref(),
                    provenance="bundle.metrics",
                )
            )
        for i, event in enumerate(self.events):
            obj_id = event.object_ref.replace(":", "-") if event.object_ref else "unknown"
            add(
                EvidenceUnit(
                    ref=f"event:{obj_id}:{event.type}:{i}",
                    kind="event",
                    label=f"{event.type} @ {event.at or 'unknown'}",
                    value={"type": event.type, "at": event.at},
                    object_ref=event.object_ref,
                    provenance=event.source,
                )
            )
            add(
                EvidenceUnit(
                    ref=f"event:{i}:{event.type}",
                    kind="event",
                    label=f"{event.type} @ {event.at or 'unknown'}",
                    value={"type": event.type, "at": event.at},
                    object_ref=event.object_ref,
                    provenance=event.source,
                )
            )
        for note in self.retrieved_evidence:
            nid = note.get("note_id") or note.get("title")
            if not nid:
                continue
            obj_id = note.get("object_id")
            add(
                EvidenceUnit(
                    ref=f"note:{nid}",
                    kind="note",
                    label=str(note.get("title") or nid),
                    value=note.get("body"),
                    object_ref=(
                        None
                        if not (note.get("object_type") and obj_id)
                        else f"{note.get('object_type')}:{obj_id}"
                    ),
                    provenance="bundle.retrieved_evidence",
                )
            )
            if obj_id:
                add(
                    EvidenceUnit(
                        ref=f"note:{obj_id}:{nid}",
                        kind="note",
                        label=str(note.get("title") or nid),
                        value=note.get("body"),
                        object_ref=(
                            None
                            if not note.get("object_type")
                            else f"{note.get('object_type')}:{obj_id}"
                        ),
                        provenance="bundle.retrieved_evidence",
                    )
                )
        for rule in self.applicable_rules:
            name = rule.get("name")
            if not name:
                continue
            version = rule.get("policy_version") or rule.get("version") or "v1"
            add(
                EvidenceUnit(
                    ref=f"rule:{name}",
                    kind="rule",
                    label=str(name),
                    value=rule.get("definition"),
                    provenance="bundle.applicable_rules",
                )
            )
            add(
                EvidenceUnit(
                    ref=f"rule:{name}:{version}",
                    kind="rule",
                    label=str(name),
                    value=rule.get("definition"),
                    provenance="bundle.applicable_rules",
                )
            )
        for policy in self.applicable_policies:
            pid = policy.get("id")
            version = policy.get("version") or "v1"
            if not pid:
                continue
            add(
                EvidenceUnit(
                    ref=f"rule:{pid}:{version}",
                    kind="rule",
                    label=str(policy.get("title") or pid),
                    value=policy.get("summary"),
                    provenance="bundle.applicable_policies",
                )
            )
        return units

    def citeable_refs(self) -> dict[str, str]:
        """Stable evidence units a model may cite. Never invent extra keys."""
        return {unit.ref: unit.kind for unit in self.evidence_units()}

    def to_dict(self) -> dict[str, Any]:
        units = self.evidence_units()
        catalog = [unit.ref for unit in units]
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
            "applicable_policies": self.applicable_policies,
            "retrieved_evidence": self.retrieved_evidence,
            "provenance": self.provenance,
            "missing_context": [asdict(m) for m in self.missing_context],
            "sufficient": self.sufficient,
            "why": self.why,
            "requirements": self.requirements,
            "evidence_units": [u.to_dict() for u in units],
            "evidence_catalog": sorted(catalog),
        }
