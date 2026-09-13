"""Operational policy refs — control logic, not warehouse observation.

PostgreSQL remains canonical business state. Policy is typed domain
code with stable ids/versions. There is no separate policy database.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CATEGORIES = (
    "data_contract",
    "context",
    "decision",
    "action",
    "security",
)


@dataclass(frozen=True)
class Policy:
    id: str
    version: str
    category: str
    title: str
    summary: str
    intents: tuple[str, ...] = ()
    implemented: bool = True

    def ref(self) -> str:
        return f"rule:{self.id}:{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "ref": self.ref(),
            "implemented": self.implemented,
        }


POLICIES: tuple[Policy, ...] = (
    Policy(
        id="resale.data-contract.source",
        version="v1",
        category="data_contract",
        title="Source data validity",
        summary=(
            "A source record becomes canonical only after a SourceAdapter, "
            "validation, and the ingest runner. Rejected rows quarantine. "
            "An LLM does not validate or ingest production rows."
        ),
    ),
    Policy(
        id="resale.context.capability-requirements",
        version="v1",
        category="context",
        title="Context requirements",
        summary=(
            "Each capability lists required concepts. Missing required "
            "context forces abstention. The model cannot override sufficiency."
        ),
    ),
    Policy(
        id="resale.decision.price-review",
        version="v1",
        category="decision",
        title="Price review without numeric markdown",
        summary=(
            "Until an operator-defined pricing policy exists, AI may recommend "
            "REVIEW PRICE, KEEP PRICE, or INSUFFICIENT EVIDENCE. It must not "
            "invent a markdown, target price, or learned optimizer."
        ),
        intents=("reprice_item",),
    ),
    Policy(
        id="resale.decision.stale-listing",
        version="v1",
        category="decision",
        title="Stale listing heuristic",
        summary=(
            "An active listing at or beyond the named stale-listing threshold "
            "is a review signal, not an automatic price change."
        ),
        intents=("reprice_item", "listing_performance", "explain_attention"),
    ),
    Policy(
        id="resale.action.human-approval",
        version="v1",
        category="action",
        title="Human approval for canonical actions",
        summary=(
            "AI may propose sandbox actions. A human approves or rejects. "
            "Approval writes internal canonical history only. No external "
            "marketplace writes."
        ),
    ),
    Policy(
        id="resale.security.future",
        version="v1",
        category="security",
        title="Security policy (not implemented)",
        summary=(
            "Authentication, authorization, tenancy, and remote-model data "
            "handling are not enforced in this runtime."
        ),
        implemented=False,
    ),
)

POLICIES_BY_ID = {p.id: p for p in POLICIES}

PRICE_RECOMMENDATIONS = frozenset(
    {"REVIEW_PRICE", "KEEP_PRICE", "INSUFFICIENT_EVIDENCE"}
)


def policies_for_intent(intent: str | None = None) -> list[Policy]:
    out: list[Policy] = []
    for policy in POLICIES:
        if not policy.intents or (intent and intent in policy.intents):
            out.append(policy)
    return out


def policy_dicts_for_intent(intent: str | None = None) -> list[dict[str, Any]]:
    return [p.to_dict() for p in policies_for_intent(intent)]
