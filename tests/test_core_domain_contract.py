"""Architecture contract: core assembly works without the resale vertical."""
from __future__ import annotations

import ast
from pathlib import Path

from cdp_cli.core.domain import Domain
from cdp_cli.core.engine import assemble_context, evaluate_sufficiency
from cdp_cli.core.model import (
    ContextObject,
    EntityRef,
    MissingContext,
    SufficiencyResult,
)

CORE_ROOT = Path(__file__).resolve().parents[1] / "src" / "cdp_cli" / "core"
FORBIDDEN = (
    "grailed",
    "depop",
    "watchers",
    "watch_rate",
    "acquisition_cost",
    "list_next",
    "reprice",
)


def _support_domain() -> Domain:
    def resolve_intent(question: str, intent: str | None = None) -> str:
        if intent:
            return intent
        text = (question or "").lower()
        if "gap" in text or "missing" in text:
            return "ticket_gap"
        return "ticket_status"

    def extract_subject(question: str, subject: str | None = None) -> str | None:
        return subject or "t-1"

    def extract_as_of(question: str, as_of: str | None = None):
        return None

    def assemble(con, *, intent, question, subject, as_of_dt):
        if intent == "ticket_gap":
            return {
                "objects": [],
                "links": [],
                "events": [],
                "facts": {},
                "metrics": {},
                "rules": [],
                "missing": [
                    MissingContext(
                        concept="sla",
                        reason="no sla clock on the ticket",
                        required_for=intent,
                    )
                ],
                "source_tools": ["dummy_tickets"],
                "source_relations": [],
            }
        ticket = ContextObject(
            "Ticket",
            subject or "t-1",
            {"title": "Printer jam", "customer_id": "c-9"},
        )
        customer = ContextObject("Customer", "c-9", {"name": "Ada"})
        return {
            "objects": [ticket, customer],
            "links": [],
            "events": [],
            "facts": {"ticket": True, "customer": True},
            "metrics": {"open_hours": 4},
            "rules": [{"name": "ack_within_hour", "kind": "rule", "applies": True}],
            "missing": [],
            "retrieved_evidence": [],
            "source_tools": ["dummy_tickets"],
            "source_relations": ["support.tickets"],
        }

    return Domain(
        name="support_test",
        intents=frozenset({"ticket_status", "ticket_gap"}),
        required_concepts={
            "ticket_status": ("ticket", "customer"),
            "ticket_gap": ("sla",),
        },
        resolve_intent=resolve_intent,
        extract_subject=extract_subject,
        extract_as_of=extract_as_of,
        assemble=assemble,
        subject_scoped=frozenset({"ticket_status", "ticket_gap"}),
        subject_name="ticket_id",
    )


def test_core_engine_assembles_a_non_resale_domain() -> None:
    bundle = assemble_context(
        con=object(),
        question="What is the status of the printer ticket?",
        domain=_support_domain(),
    )
    assert bundle.intent == "ticket_status"
    assert bundle.sufficient is True
    assert bundle.provenance["domain"] == "support_test"
    types = {obj.type for obj in bundle.objects}
    assert types == {"Ticket", "Customer"}
    assert "grailed" not in bundle.to_dict().__repr__().lower()
    assert "watchers" not in str(bundle.metrics)


def test_core_engine_reports_insufficient_without_resale_concepts() -> None:
    bundle = assemble_context(
        con=object(),
        question="What SLA is missing on this ticket gap?",
        domain=_support_domain(),
    )
    assert bundle.sufficient is False
    assert [m.concept for m in bundle.missing_context] == ["sla"]
    assert "sla" in bundle.why


def test_sufficiency_helper_is_domain_neutral() -> None:
    missing = [
        MissingContext(concept="copy_count", reason="none", required_for="hold")
    ]
    result = evaluate_sufficiency(
        intent="hold", required=("copy_count",), missing=missing
    )
    assert isinstance(result, SufficiencyResult)
    assert result.sufficient is False
    assert "copy_count" in result.why


def test_entity_ref_is_domain_neutral() -> None:
    ref = EntityRef("Ticket", "t-1")
    assert str(ref) == "Ticket:t-1"


def _string_literals(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        if isinstance(node, ast.Name):
            out.append(node.id)
        if isinstance(node, ast.Attribute):
            out.append(node.attr)
    return out


def test_core_package_has_no_resale_vocabulary() -> None:
    hits: list[str] = []
    for path in CORE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text())
        blob = " ".join(_string_literals(tree)).lower()
        for word in FORBIDDEN:
            if word in blob:
                hits.append(f"{path.name}:{word}")
    assert hits == []
