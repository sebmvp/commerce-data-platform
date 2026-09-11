"""Domain extension seam.

A vertical registers object resolvers, intents, metrics, and rules.
The core does not learn business vocabulary from that registration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from .model import ContextRequirement


class IntentResolver(Protocol):
    def __call__(self, question: str, intent: str | None = None) -> str: ...


class SubjectExtractor(Protocol):
    def __call__(self, question: str, subject: str | None = None) -> str | None: ...


class AsOfExtractor(Protocol):
    def __call__(self, question: str, as_of: str | None = None) -> datetime | None: ...


class IntentAssembler(Protocol):
    def __call__(
        self,
        con: Any,
        *,
        intent: str,
        question: str,
        subject: str | None,
        as_of_dt: datetime | None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Domain:
    """Smallest useful vertical registration.

    Not a plugin marketplace. A second domain is Python composition:
    provide these callables without rewriting ContextBundle or the
    FastAPI/MCP adapters.
    """

    name: str
    intents: frozenset[str]
    required_concepts: dict[str, tuple[str, ...]]
    resolve_intent: IntentResolver
    extract_subject: SubjectExtractor
    extract_as_of: AsOfExtractor
    assemble: IntentAssembler
    subject_scoped: frozenset[str] = field(default_factory=frozenset)
    subject_name: str = "subject"
    entity_types: tuple[str, ...] = ()
    relationship_types: tuple[tuple[str, str, str], ...] = ()
    action_types: frozenset[str] = field(default_factory=frozenset)

    def requirements_for(self, intent: str) -> tuple[ContextRequirement, ...]:
        return tuple(
            ContextRequirement(concept=concept, intent=intent)
            for concept in self.required_concepts.get(intent, ())
        )


_active: Domain | None = None


def register_domain(domain: Domain) -> Domain:
    global _active
    _active = domain
    return domain


def get_active_domain() -> Domain:
    """Default production domain is resale; tests may register another."""
    global _active
    if _active is None:
        from cdp_cli.domains.resale.domain import RESALE

        _active = RESALE
    return _active
