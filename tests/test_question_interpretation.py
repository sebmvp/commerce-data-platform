"""Question interpretation: paraphrases reach registered capabilities."""
from __future__ import annotations

from cdp_cli.llm.planner import deterministic_plan


def test_paraphrases_resolve_to_registered_capabilities() -> None:
    cases = [
        ("Is the asking price on j4-military-s too high?", "reprice_item", "j4-military-s"),
        ("What should I work on today?", "focus_today", None),
        ("Why is stone-cargo-l in the queue?", "explain_attention", "stone-cargo-l"),
        ("Can I trust this warehouse?", "data_health", None),
        ("What changed since the previous snapshot?", "recent_changes", None),
    ]
    for question, capability, subject in cases:
        plan = deterministic_plan(question)
        assert plan.capability == capability, question
        if subject:
            assert plan.subject == subject
