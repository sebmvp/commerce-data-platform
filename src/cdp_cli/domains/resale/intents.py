"""Bounded question intents. v1 does not do free-form NL planning."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from ...clock import reference_now

INTENTS = frozenset({
    "reprice_item",
    "focus_today",
    "explain_attention",
    "item_state",
    "item_history",
    "data_health",
    "recent_changes",
    "hybrid_notes",
    "listing_as_of",
    "compare_channels",
    "listing_performance",
})

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
    "hybrid_notes": ("retrieved_evidence",),
    "listing_as_of": ("item", "listing_as_of"),
    "compare_channels": ("unlisted_owned", "capital_tied_up", "channel_history"),
    "listing_performance": ("watch_rate", "offers"),
}

ITEM_SCOPED = frozenset({
    "reprice_item",
    "explain_attention",
    "item_state",
    "item_history",
    "listing_as_of",
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
    if "note" in text or "policy" in text or "playbook" in text:
        return "hybrid_notes"
    if "trust" in text or "data health" in text or "can i trust" in text:
        return "data_health"
    if "changed" in text or "previous snapshot" in text:
        return "recent_changes"
    if "two weeks ago" in text or "listing state" in text or "as-of" in text or "as of" in text:
        return "listing_as_of"
    if "channel" in text and ("historically" in text or "better" in text or "compare" in text):
        return "compare_channels"
    if ("attention" in text and "offer" in text) or "watch_rate" in text or "weak offer" in text:
        return "listing_performance"
    if "reprice" in text or "price too" in text or "too high" in text or "asking price" in text:
        return "reprice_item"
    if "why" in text and ("attention" in text or "recommend" in text or "queue" in text):
        return "explain_attention"
    if "unlisted" in text or "how many items" in text:
        return "focus_today"
    if ("what should i do about" in text or "what should i do" in text) and _SKU_RE.search(text):
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


def extract_as_of(question: str, as_of: str | None = None) -> datetime | None:
    if as_of and str(as_of).strip():
        text = str(as_of).strip()
        text = text.removesuffix("Z")
        return datetime.fromisoformat(text)
    q = (question or "").lower()
    now = reference_now()
    if "two weeks ago" in q or "14 days ago" in q:
        return now - timedelta(days=14)
    if "last week" in q or "a week ago" in q or "7 days ago" in q:
        return now - timedelta(days=7)
    return None
