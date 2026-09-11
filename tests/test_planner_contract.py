"""QuestionPlan validation. The model may not emit SQL or unknown tools."""
from __future__ import annotations

import json

from cdp_cli.llm.planner import plan_question


class EnvScripted:
    name = "env"
    model = "scripted"

    def __init__(self, output: str) -> None:
        self.output = output

    def complete(self, prompt: str) -> str:
        del prompt
        return self.output


def test_unknown_capability_falls_back_deterministically() -> None:
    plan = plan_question(
        "Should I reprice j4-military-s?",
        provider=EnvScripted(json.dumps({"capability": "drop_table"})),
    )
    assert plan.source == "deterministic_fallback"
    assert plan.capability == "reprice_item"


def test_unknown_subject_type_falls_back() -> None:
    plan = plan_question(
        "Should I reprice j4-military-s?",
        provider=EnvScripted(
            json.dumps(
                {
                    "capability": "reprice_item",
                    "subject": "j4-military-s",
                    "subject_type": "Spaceship",
                }
            )
        ),
    )
    assert plan.source == "deterministic_fallback"


def test_invalid_as_of_falls_back() -> None:
    plan = plan_question(
        "Should I reprice j4-military-s?",
        provider=EnvScripted(
            json.dumps(
                {
                    "capability": "reprice_item",
                    "subject": "j4-military-s",
                    "as_of": "next tuesday-ish",
                }
            )
        ),
    )
    assert plan.source == "deterministic_fallback"


def test_unexpected_fields_fall_back() -> None:
    plan = plan_question(
        "Should I reprice j4-military-s?",
        provider=EnvScripted(
            json.dumps(
                {
                    "capability": "reprice_item",
                    "sql": "SELECT * FROM catalog.items",
                }
            )
        ),
    )
    assert plan.source == "deterministic_fallback"


def test_unknown_filters_fall_back() -> None:
    plan = plan_question(
        "Should I reprice j4-military-s?",
        provider=EnvScripted(
            json.dumps(
                {
                    "capability": "reprice_item",
                    "subject": "j4-military-s",
                    "filters": {"brand": "Nike"},
                }
            )
        ),
    )
    assert plan.source == "deterministic_fallback"


def test_valid_llm_plan_is_accepted() -> None:
    plan = plan_question(
        "hmm about j4-military-s maybe?",
        provider=EnvScripted(
            json.dumps(
                {
                    "capability": "reprice_item",
                    "subject": "j4-military-s",
                    "subject_type": "Item",
                }
            )
        ),
    )
    assert plan.source == "llm"
    assert plan.capability == "reprice_item"
    assert plan.subject == "j4-military-s"


def test_malformed_planner_json_falls_back() -> None:
    plan = plan_question(
        "Should I reprice j4-military-s?",
        provider=EnvScripted("not-json"),
    )
    assert plan.source == "deterministic_fallback"
    assert plan.capability == "reprice_item"
