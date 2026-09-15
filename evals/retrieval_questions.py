"""Gold set for unstructured note/policy/playbook retrieval.

This scores the note retriever, not assemble_context and not the
TF-IDF lexical baseline over serialized warehouse rows.

Cases cover exact terms, keyword combinations, shared-lexeme
paraphrases, object scope, policies, playbooks, and negatives.
`semantic_paraphrase` marks questions that share little surface
lexicon with the expected note — a miss there is a vector-search
gate, not an FTS implementation failure.
"""

from __future__ import annotations

from typing import Any

# Small corpus: sample_data/notes.jsonl (five notes). Do not grow this
# into a general IR benchmark.

CASES: list[dict[str, Any]] = [
    {
        "id": "R01",
        "question": "stale listing playbook",
        "expected_note_ids": ["playbook-stale-listing"],
        "tags": ["exact", "playbook"],
    },
    {
        "id": "R02",
        "question": "high watch rate with zero offers",
        "expected_note_ids": ["playbook-stale-listing"],
        "tags": ["keywords", "playbook"],
    },
    {
        "id": "R03",
        "question": "review price of old listings",
        "expected_note_ids": ["playbook-stale-listing"],
        "tags": ["paraphrase", "playbook"],
    },
    {
        "id": "R04",
        "question": "oil mark studio",
        "object_id": "stone-cargo-l",
        "expected_note_ids": ["note-stone-cargo-photo"],
        "unexpected_note_ids": [
            "playbook-stale-listing",
            "policy-grailed-fees",
            "note-j4-military-wear",
        ],
        "tags": ["object_scoped", "keywords"],
    },
    {
        "id": "R05",
        "question": "What does the Grailed seller fee policy say?",
        "expected_note_ids": ["policy-grailed-fees"],
        "tags": ["policy", "natural_question"],
    },
    {
        "id": "R06",
        "question": "What does the stale listing playbook recommend?",
        "expected_note_ids": ["playbook-stale-listing"],
        "tags": ["playbook", "natural_question"],
    },
    {
        "id": "R07",
        "question": "customer return insurance claims process",
        "expected_note_ids": [],
        "expect_empty": True,
        "tags": ["negative"],
    },
    {
        "id": "R08",
        "question": "Photography backlog",
        "expected_note_ids": ["note-stone-cargo-photo"],
        "tags": ["exact_title"],
    },
    {
        "id": "R09",
        "question": "studio photos delayed for cargo pants",
        "expected_note_ids": ["note-stone-cargo-photo"],
        "tags": ["paraphrase"],
    },
    {
        "id": "R10",
        "question": "White Cement 3s drawing saves but no offers",
        "expected_note_ids": ["note-watchy-price"],
        "tags": ["keywords", "seller_note"],
    },
    {
        "id": "R11",
        "question": "inner-sole wear military black",
        "expected_note_ids": ["note-j4-military-wear"],
        "tags": ["keywords", "seller_note"],
    },
    {
        "id": "R12",
        "question": "",
        "object_id": "j4-military-s",
        "expected_note_ids": ["note-j4-military-wear"],
        "unexpected_note_ids": [
            "note-stone-cargo-photo",
            "policy-grailed-fees",
            "playbook-stale-listing",
        ],
        "tags": ["object_scoped"],
    },
    {
        "id": "R13",
        "question": "Grailed seller fee",
        "object_id": "j4-military-s",
        "expected_note_ids": [],
        "expect_empty": True,
        "unexpected_note_ids": ["policy-grailed-fees"],
        "tags": ["object_scoped", "negative"],
    },
    {
        "id": "R14",
        "question": "price-friction signal",
        "expected_note_ids": ["playbook-stale-listing"],
        "tags": ["exact_phrase"],
    },
    {
        "id": "R15",
        "question": "What should we do when something has been on the site too long and nobody bought it?",
        "expected_note_ids": ["playbook-stale-listing"],
        "semantic_paraphrase": True,
        "tags": ["semantic", "playbook"],
    },
    {
        "id": "R16",
        "question": "how much does Grailed take from a sale",
        "expected_note_ids": ["policy-grailed-fees"],
        "tags": ["paraphrase", "policy"],
    },
    {
        "id": "R17",
        "question": "oil mark on the hem still unlisted",
        "expected_note_ids": ["note-stone-cargo-photo"],
        "tags": ["keywords"],
    },
    {
        "id": "R18",
        "question": "authentication hologram for imported cameras",
        "expected_note_ids": [],
        "expect_empty": True,
        "tags": ["negative"],
    },
    {
        "id": "R19",
        "question": "seller fee on the sale price",
        "kind": "policy",
        "expected_note_ids": ["policy-grailed-fees"],
        "unexpected_note_ids": ["playbook-stale-listing"],
        "tags": ["kind_filter", "policy"],
    },
    {
        "id": "R20",
        "question": "call it used not like-new",
        "expected_note_ids": ["note-j4-military-wear"],
        "tags": ["exact_phrase"],
    },
    {
        "id": "R21",
        "question": "How do we talk about worn insoles without overselling condition?",
        "expected_note_ids": ["note-j4-military-wear"],
        "tags": ["paraphrase", "seller_note"],
    },
]
