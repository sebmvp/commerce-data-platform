"""Domain extension seam.

A vertical registers object resolvers, intents, metrics, rules, and
bounded AI capabilities. The core does not learn business vocabulary
from that registration.
"""
from __future__ import annotations

from collections.abc import Callable
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


class ActionValidator(Protocol):
    def __call__(self, action: dict[str, Any]) -> str | None: ...


class ActionApplier(Protocol):
    def __call__(
        self, con: Any, rec: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]: ...


@dataclass(frozen=True)
class ReadToolSpec:
    """Registered READ capability the Business Librarian may invoke."""

    name: str
    summary: str
    capability: str
    needs_subject: bool = False


def _default_validate_action(action: dict[str, Any]) -> str | None:
    del action
    return None


def _default_apply_action(
    con: Any, rec: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    del con
    raise ValueError(f"cannot apply action_type {rec.get('action_type')}")


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
    target_types: frozenset[str] = field(default_factory=frozenset)
    read_tools: dict[str, ReadToolSpec] = field(default_factory=dict)
    capability_tools: dict[str, tuple[str, ...]] = field(default_factory=dict)
    validate_action: ActionValidator = _default_validate_action
    apply_action: ActionApplier = _default_apply_action
    recommendation_actions: dict[str, str] = field(default_factory=dict)
    on_action_applied: Callable[[Any], None] = field(default=lambda con: None)

    def requirements_for(self, intent: str) -> tuple[ContextRequirement, ...]:
        return tuple(
            ContextRequirement(concept=concept, intent=intent)
            for concept in self.required_concepts.get(intent, ())
        )

    def tools_for_capability(self, capability: str) -> tuple[str, ...]:
        return self.capability_tools.get(capability, ())

    def sandbox_type_for_recommendation(self, rec_action: str) -> str:
        try:
            return self.recommendation_actions[rec_action]
        except KeyError as exc:
            raise ValueError(f"unknown recommendation action {rec_action!r}") from exc


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


def reset_active_domain() -> None:
    """Test helper. Production code should not call this."""
    global _active
    _active = None
