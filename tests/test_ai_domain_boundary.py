"""Architecture contract: generic AI runtime has no resale vocabulary."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from cdp_cli.core.domain import Domain, ReadToolSpec, reset_active_domain
from cdp_cli.core.engine import assemble_context
from cdp_cli.core.model import ContextObject, MissingContext
from cdp_cli.llm.grounding import parse_grounded
from cdp_cli.llm.librarian import run_librarian
from cdp_cli.llm.providers import FakeProvider

LLM_ROOT = Path(__file__).resolve().parents[1] / "src" / "cdp_cli" / "llm"
ACTIONS = Path(__file__).resolve().parents[1] / "src" / "cdp_cli" / "actions.py"
FORBIDDEN = (
    "propose_reprice",
    "listing_performance",
    "review_price",
    "keep_price",
    "grailed",
    "reprice_item",
    "watch_rate",
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
        del con, question, as_of_dt
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
        return {
            "objects": [ticket],
            "links": [],
            "events": [],
            "facts": {"ticket": True, "open": True},
            "metrics": {"open_hours": 4},
            "rules": [{"id": "ack-v1", "version": "v1", "name": "ack_within_hour"}],
            "missing": [],
            "retrieved_evidence": [],
            "source_tools": ["dummy_tickets"],
            "source_relations": ["support.tickets"],
        }

    def validate_action(action: dict) -> str | None:
        if action.get("action_type") != "close_ticket":
            return f"unknown action_type {action.get('action_type')!r}"
        if action.get("target_type") != "ticket":
            return "target_type must be ticket"
        return None

    tools = {
        "ticket_status": ReadToolSpec(
            "ticket_status", "loaded ticket", "ticket_status", True
        ),
        "ticket_gap": ReadToolSpec("ticket_gap", "loaded ticket gap", "ticket_gap"),
    }
    return Domain(
        name="support_test",
        intents=frozenset({"ticket_status", "ticket_gap"}),
        required_concepts={
            "ticket_status": ("ticket",),
            "ticket_gap": ("sla",),
        },
        resolve_intent=resolve_intent,
        extract_subject=extract_subject,
        extract_as_of=extract_as_of,
        assemble=assemble,
        subject_scoped=frozenset({"ticket_status", "ticket_gap"}),
        subject_name="ticket_id",
        entity_types=("Ticket",),
        action_types=frozenset({"close_ticket"}),
        target_types=frozenset({"ticket"}),
        read_tools=tools,
        capability_tools={
            "ticket_status": ("ticket_status",),
            "ticket_gap": ("ticket_gap",),
        },
        validate_action=validate_action,
    )


def _literals(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        if isinstance(node, ast.Name):
            out.append(node.id)
        if isinstance(node, ast.Attribute):
            out.append(node.attr)
    return out


def test_generic_ai_modules_have_no_resale_vocabulary() -> None:
    hits: list[str] = []
    paths = list(LLM_ROOT.glob("*.py")) + [ACTIONS]
    for path in paths:
        tree = ast.parse(path.read_text())
        blob = " ".join(_literals(tree)).lower()
        for word in FORBIDDEN:
            if word in blob:
                hits.append(f"{path.name}:{word}")
    assert hits == []


def test_dummy_domain_librarian_without_resale() -> None:
    domain = _support_domain()
    result = run_librarian(
        object(),
        question="What is the status of the printer ticket?",
        domain=domain,
        provider=FakeProvider(),
    )
    assert result["plan"]["capability"] == "ticket_status"
    assert result["plan"]["domain"] == "support_test"
    assert result["bundle"]["sufficient"] is True
    assert result["tool_trace"][0]["tool"] == "ticket_status"
    assert "grailed" not in json.dumps(result).lower()
    reset_active_domain()


def test_dummy_domain_action_validation() -> None:
    domain = _support_domain()
    bundle = assemble_context(
        object(),
        question="status of t-1",
        domain=domain,
    )
    ok = parse_grounded(
        json.dumps(
            {
                "answer": "Ticket t-1 is open.",
                "abstained": False,
                "evidence_refs": ["object:Ticket:t-1"],
                "caveats": [],
                "suggested_action": {
                    "action_type": "close_ticket",
                    "target_type": "ticket",
                    "target_id": "t-1",
                    "payload": {},
                },
            }
        ),
        bundle,
        domain,
    )
    assert ok["ok"] is True
    bad = parse_grounded(
        json.dumps(
            {
                "answer": "reprice it",
                "abstained": False,
                "evidence_refs": ["object:Ticket:t-1"],
                "caveats": [],
                "suggested_action": {
                    "action_type": "propose_reprice",
                    "target_type": "item",
                    "target_id": "t-1",
                    "payload": {},
                },
            }
        ),
        bundle,
        domain,
    )
    assert bad["ok"] is False
    assert "propose_reprice" in str(bad["reason"])
