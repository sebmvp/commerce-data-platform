"""Resale vertical registration."""
from __future__ import annotations

from ...core.domain import Domain
from .actions import ACTION_TYPES, TARGET_TYPES, apply_action, validate_action
from .assemble import assemble_resale
from .intents import (
    INTENTS,
    ITEM_SCOPED,
    REQUIRED_CONCEPTS,
    extract_as_of,
    extract_sku,
    resolve_intent,
)
from .services import capture_business_snapshot
from .tools import CAPABILITY_TOOLS, READ_TOOLS, RECOMMENDATION_ACTIONS


def _extract_subject(question: str, subject: str | None = None) -> str | None:
    return extract_sku(question, subject)


def _on_action_applied(con) -> None:
    capture_business_snapshot(con, trigger="action_apply")


RESALE = Domain(
    name="resale",
    intents=INTENTS,
    required_concepts=REQUIRED_CONCEPTS,
    resolve_intent=resolve_intent,
    extract_subject=_extract_subject,
    extract_as_of=extract_as_of,
    assemble=assemble_resale,
    subject_scoped=ITEM_SCOPED,
    subject_name="sku",
    entity_types=("Item", "Listing", "Channel", "Order", "EngagementObservation"),
    relationship_types=(
        ("Item", "HAS_LISTING", "Listing"),
        ("Listing", "ON_CHANNEL", "Channel"),
        ("Listing", "HAS_ENGAGEMENT", "EngagementObservation"),
        ("Listing", "RESULTED_IN", "Order"),
    ),
    action_types=ACTION_TYPES,
    target_types=TARGET_TYPES,
    read_tools=READ_TOOLS,
    capability_tools=CAPABILITY_TOOLS,
    validate_action=validate_action,
    apply_action=apply_action,
    recommendation_actions=RECOMMENDATION_ACTIONS,
    on_action_applied=_on_action_applied,
)
