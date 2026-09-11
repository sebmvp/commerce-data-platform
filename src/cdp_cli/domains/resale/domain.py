"""Resale vertical registration."""
from __future__ import annotations

from ...core.domain import Domain
from .assemble import assemble_resale
from .intents import (
    INTENTS,
    ITEM_SCOPED,
    REQUIRED_CONCEPTS,
    extract_as_of,
    extract_sku,
    resolve_intent,
)


def _extract_subject(question: str, subject: str | None = None) -> str | None:
    return extract_sku(question, subject)


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
    action_types=frozenset(
        {"propose_list", "propose_reprice", "propose_channel_change", "mark_reviewed"}
    ),
)
