"""Resale Analyst read-tool registry.

The generic analyst loop consumes these specs. It does not know what
a listing or SKU is.
"""
from __future__ import annotations

from cdp_cli.core.domain import ReadToolSpec

READ_TOOLS: dict[str, ReadToolSpec] = {
    "business_snapshot": ReadToolSpec(
        "business_snapshot", "queried business snapshot", "focus_today"
    ),
    "attention_queue": ReadToolSpec(
        "attention_queue", "queried attention queue", "focus_today"
    ),
    "item_state": ReadToolSpec(
        "item_state", "loaded item state", "item_state", needs_subject=True
    ),
    "item_history": ReadToolSpec(
        "item_history", "loaded item history", "item_history", needs_subject=True
    ),
    "listing_performance": ReadToolSpec(
        "listing_performance", "loaded listing performance", "listing_performance"
    ),
    "channel_comparison": ReadToolSpec(
        "channel_comparison", "compared channels", "compare_channels"
    ),
    "recent_changes": ReadToolSpec(
        "recent_changes", "loaded recent changes", "recent_changes"
    ),
    "data_health": ReadToolSpec(
        "data_health", "loaded data health", "data_health"
    ),
    "note_evidence": ReadToolSpec(
        "note_evidence", "retrieved note/policy evidence", "hybrid_notes"
    ),
}

CAPABILITY_TOOLS: dict[str, tuple[str, ...]] = {
    "reprice_item": ("item_state", "item_history", "listing_performance"),
    "focus_today": ("business_snapshot", "attention_queue", "data_health"),
    "explain_attention": ("attention_queue", "item_state"),
    "item_state": ("item_state",),
    "item_history": ("item_history",),
    "data_health": ("data_health",),
    "recent_changes": ("recent_changes",),
    "hybrid_notes": ("note_evidence",),
    "listing_as_of": ("item_state", "item_history"),
    "compare_channels": ("channel_comparison",),
    "listing_performance": ("listing_performance",),
}

RECOMMENDATION_ACTIONS = {
    "list_next": "propose_list",
    "review_price_or_channel": "propose_reprice",
    "consider_reprice": "propose_reprice",
    "monitor": "mark_reviewed",
}
