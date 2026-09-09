"""Bounded question intents. v1 does not do free-form NL planning."""
from __future__ import annotations

import re

INTENTS = frozenset({
    "reprice_item",
    "focus_today",
    "explain_attention",
    "item_state",
    "item_history",
    "data_health",
    "recent_changes",
})

# Concepts the engine must retrieve or explicitly mark missing.
REQUIRED_CONCEPTS: dict[str, tuple[str, ...]] = {
    "reprice_item": (
        "item",
        "listing",
        "listing_age",
        "asking_price",
        "acquisition_cost",
        "engagement",
        "item_history",
        "repricing_policy",
    ),
    "focus_today": ("snapshot", "attention_queue", "warehouse_trust"),
    "explain_attention": (
        "item",
        "attention_reason",
        "supporting_metrics",
        "applicable_rules",
    ),
    "item_state": ("item", "listings", "orders"),
    "item_history": ("item", "events"),
    "data_health": ("warehouse_trust",),
    "recent_changes": ("previous_snapshot",),
}

ITEM_SCOPED = frozenset({
    "reprice_item",
    "explain_attention",
    "item_state",
    "item_history",
})

_SKU_RE = re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", re.IGNORECASE)


def resolve_intent(question: str, intent: str | None = None) -> str:
    if intent:
        intent = intent.strip()
        if intent not in INTENTS:
            known = ", ".join(sorted(INTENTS))
            raise ValueError(f"unknown intent {intent!r}; known: {known}")
        return intent
    text = (question or "").strip().lower()
    if not text:
        raise ValueError("question or intent is required")
    if "trust" in text or "data health" in text or "can i trust" in text:
        return "data_health"
    if "changed" in text or "previous snapshot" in text:
        return "recent_changes"
    if "reprice" in text or "price too" in text:
        return "reprice_item"
    if "why" in text and ("attention" in text or "recommend" in text or "queue" in text):
        return "explain_attention"
    if "focus" in text or "today" in text or "what should i" in text:
        return "focus_today"
    if "history" in text or "what happened" in text:
        return "item_history"
    if _SKU_RE.search(text):
        return "item_state"
    raise ValueError(
        "could not resolve intent from question; pass intent= explicitly"
    )


def extract_sku(question: str, sku: str | None = None) -> str | None:
    if sku and str(sku).strip():
        return str(sku).strip()
    matches = _SKU_RE.findall(question or "")
    return matches[-1] if matches else None
