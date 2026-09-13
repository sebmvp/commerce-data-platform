"""Source contract proposals. Status is always PROPOSED until a human approves.

The LLM may interpret a profile. It does not write canonical records,
change schema, or activate an adapter.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .profile import profile_file

KNOWN_ITEM_FIELDS = {
    "sku": "sku",
    "product": "product",
    "title": "product",
    "name": "product",
    "variant": "variant",
    "size": "size",
    "category": "category_key",
    "category_key": "category_key",
    "condition": "condition",
    "status": "status",
    "qty": "qty",
    "quantity": "qty",
    "acquisition_cost_cny": "acquisition_cost_cny",
    "cost_cny": "acquisition_cost_cny",
    "target_price_usd": "target_price_usd",
    "notes": "notes",
}

KNOWN_LISTING_FIELDS = {
    "platform": "platform",
    "price_usd": "price_usd",
    "listed_at": "listed_at",
    "sold_at": "sold_at",
    "sold_price_usd": "sold_price_usd",
    "platform_url": "platform_url",
}

AMBIGUOUS_NAMES = frozenset(
    {
        "amount",
        "price",
        "cost",
        "value",
        "id",
        "date",
        "time",
        "name",
        "type",
        "status",
        "currency",
        "unit",
    }
)


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: str
    target_field: str | None = None
    entity: str | None = None
    notes: str | None = None


class SourceContractProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "PROPOSED"
    source_name: str
    source_type: str
    entity_mappings: list[str] = Field(default_factory=list)
    field_mappings: list[FieldMapping] = Field(default_factory=list)
    candidate_natural_keys: list[str] = Field(default_factory=list)
    timestamp_semantics: dict[str, str] = Field(default_factory=dict)
    units_currency: dict[str, str] = Field(default_factory=dict)
    required_fields: list[str] = Field(default_factory=list)
    nullable_fields: list[str] = Field(default_factory=list)
    validation_rules: list[str] = Field(default_factory=list)
    provenance_mappings: dict[str, str] = Field(default_factory=dict)
    ambiguous_fields: list[str] = Field(default_factory=list)
    human_questions: list[str] = Field(default_factory=list)
    unmapped_fields: list[str] = Field(default_factory=list)
    proposed_quality_tests: list[str] = Field(default_factory=list)


def _heuristic_proposal(profile: dict[str, Any]) -> SourceContractProposal:
    mappings: list[FieldMapping] = []
    ambiguous: list[str] = []
    unmapped: list[str] = []
    questions: list[str] = []
    timestamps: dict[str, str] = {}
    units: dict[str, str] = {}
    entities: set[str] = set()
    required: list[str] = []
    nullable: list[str] = []

    for field in profile.get("fields") or []:
        name = str(field.get("name") or "")
        lower = name.lower()
        null_freq = field.get("null_frequency") or 0
        if null_freq and float(null_freq) > 0:
            nullable.append(name)
        else:
            required.append(name)
        if field.get("date_like"):
            timestamps[name] = "date-like; confirm event vs observed vs effective time"
            questions.append(
                f"What instant does {name!r} represent "
                "(observed_at, effective_at, listed_at, sold_at)?"
            )
        if lower in KNOWN_ITEM_FIELDS:
            entities.add("Item")
            mappings.append(
                FieldMapping(
                    source_field=name,
                    target_field=KNOWN_ITEM_FIELDS[lower],
                    entity="Item",
                )
            )
            if "cny" in lower:
                units[name] = "CNY (from field name; confirm)"
            if "usd" in lower:
                units[name] = "USD (from field name; confirm)"
            continue
        if lower in KNOWN_LISTING_FIELDS:
            entities.add("Listing")
            mappings.append(
                FieldMapping(
                    source_field=name,
                    target_field=KNOWN_LISTING_FIELDS[lower],
                    entity="Listing",
                )
            )
            continue
        if lower in AMBIGUOUS_NAMES or lower in {"price", "cost", "amount"}:
            ambiguous.append(name)
            questions.append(
                f"What does {name!r} mean in this source "
                "(entity, unit/currency, required vs optional)?"
            )
            continue
        unmapped.append(name)
        questions.append(f"Should {name!r} map to a canonical field, be ignored, or stay evidence-only?")

    if "sku" not in {m.source_field.lower() for m in mappings}:
        questions.append("Which field is the item natural key if not sku?")

    keys = list(profile.get("candidate_natural_keys") or [])
    tests = [
        "row_count matches source",
        "natural key uniqueness",
        "required fields non-null after mapping",
        "timestamp parseable or quarantined",
    ]
    return SourceContractProposal(
        status="PROPOSED",
        source_name=str(profile.get("source_name") or "source"),
        source_type=str(profile.get("source_type") or "unknown"),
        entity_mappings=sorted(entities) or ["Item"],
        field_mappings=mappings,
        candidate_natural_keys=keys,
        timestamp_semantics=timestamps,
        units_currency=units,
        required_fields=required,
        nullable_fields=nullable,
        validation_rules=[
            "adapter must not write invalid rows",
            "ingest runner owns quarantine and lineage",
        ],
        provenance_mappings={
            "source_system": str(profile.get("source_name") or "source"),
            "source_record_reference": keys[0] if keys else "row-index (confirm)",
        },
        ambiguous_fields=ambiguous,
        human_questions=questions,
        unmapped_fields=unmapped,
        proposed_quality_tests=tests,
    )


def _proposal_prompt(profile: dict[str, Any]) -> str:
    compact = {
        "source_name": profile.get("source_name"),
        "source_type": profile.get("source_type"),
        "row_count": profile.get("row_count"),
        "fields": [
            {
                "name": f.get("name"),
                "inferred_type": f.get("inferred_type"),
                "null_frequency": f.get("null_frequency"),
                "distinct_count": f.get("distinct_count"),
                "date_like": f.get("date_like"),
                "sample_values": f.get("sample_values"),
            }
            for f in profile.get("fields") or []
        ],
        "candidate_natural_keys": profile.get("candidate_natural_keys"),
    }
    schema = SourceContractProposal.model_json_schema()
    return (
        "Propose a SourceContract for this profile. Return JSON only matching "
        "the schema. Do not invent business semantics. Ambiguous fields must "
        "become human_questions, not guessed mappings. status must be PROPOSED. "
        "Do not include extra fields.\n"
        f"schema: {json.dumps(schema)}\n"
        f"profile: {json.dumps(compact, default=str)}"
    )


def propose_from_profile(
    profile: dict[str, Any],
    *,
    provider: Any | None = None,
) -> dict[str, Any]:
    heuristic = _heuristic_proposal(profile)
    used = provider
    if used is not None and getattr(used, "name", "fake") not in {"fake", "scripted"}:
        try:
            raw = used.complete(_proposal_prompt(profile))
            payload = json.loads(raw)
            parsed = SourceContractProposal.model_validate(payload)
            parsed.status = "PROPOSED"
            proposal = parsed.model_dump()
            proposal["proposal_source"] = "llm"
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError, KeyError):
            proposal = heuristic.model_dump()
            proposal["proposal_source"] = "deterministic_fallback"
    else:
        proposal = heuristic.model_dump()
        proposal["proposal_source"] = "deterministic"
    proposal["status"] = "PROPOSED"
    proposal["profile"] = profile
    proposal["approval"] = (
        "Human review required. This proposal does not ingest, "
        "alter schema, or activate an adapter."
    )
    return proposal


def propose_file(path: str | Path, *, provider: Any | None = None) -> dict[str, Any]:
    profile = profile_file(path)
    return propose_from_profile(profile, provider=provider)


def review_proposal(payload: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(payload, (str, Path)):
        path = Path(payload)
        if path.is_file():
            data = json.loads(path.read_text())
        else:
            data = json.loads(str(payload))
    else:
        data = payload
    if not isinstance(data, dict):
        raise TypeError("proposal is not an object")
    data["status"] = data.get("status") or "PROPOSED"
    if data["status"] != "PROPOSED":
        data["review_note"] = (
            f"status {data['status']!r} is not an approved ingest contract. "
            "Only a human-approved contract may feed a deterministic adapter."
        )
    else:
        data["review_note"] = (
            "PROPOSED. Answer human_questions before approving. "
            "Approval is a human step; this command does not activate ingest."
        )
    data["canonical_ingest"] = (
        "Deterministic SourceAdapter + validation + ingest runner remains "
        "the only write path into PostgreSQL."
    )
    return data
