"""Reusable context infrastructure. Verticals live under cdp_cli.domains."""

from .domain import Domain, get_active_domain, register_domain
from .engine import assemble_context, evaluate_sufficiency
from .model import (
    ContextBundle,
    ContextEvent,
    ContextLink,
    ContextObject,
    ContextRequirement,
    EntityRef,
    MissingContext,
    SufficiencyResult,
)
from .plan import QuestionPlan

__all__ = [
    "ContextBundle",
    "ContextEvent",
    "ContextLink",
    "ContextObject",
    "ContextRequirement",
    "Domain",
    "EntityRef",
    "MissingContext",
    "QuestionPlan",
    "SufficiencyResult",
    "assemble_context",
    "evaluate_sufficiency",
    "get_active_domain",
    "register_domain",
]
