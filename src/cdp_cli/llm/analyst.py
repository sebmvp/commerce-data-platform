"""Analyst Agent V1: bounded read-only loop over registered capabilities.

The agent does not emit SQL, run Python, walk the filesystem, or call
the network. Business facts are always re-resolved from the platform.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ..core.engine import assemble_context
from ..core.plan import QuestionPlan
from .gateway import LLMProvider, get_provider, is_real_provider_name
from .grounding import ground_from_bundle
from .planner import deterministic_plan, plan_question

MAX_ITERATIONS = 4

REGISTERED_TOOLS = {
    "business_snapshot": {
        "summary": "queried business snapshot",
        "capability": "focus_today",
        "needs_subject": False,
    },
    "attention_queue": {
        "summary": "queried attention queue",
        "capability": "focus_today",
        "needs_subject": False,
    },
    "item_state": {
        "summary": "loaded item state",
        "capability": "item_state",
        "needs_subject": True,
    },
    "item_history": {
        "summary": "loaded item history",
        "capability": "item_history",
        "needs_subject": True,
    },
    "listing_performance": {
        "summary": "loaded listing performance",
        "capability": "listing_performance",
        "needs_subject": False,
    },
    "channel_comparison": {
        "summary": "compared channels",
        "capability": "compare_channels",
        "needs_subject": False,
    },
    "recent_changes": {
        "summary": "loaded recent changes",
        "capability": "recent_changes",
        "needs_subject": False,
    },
    "data_health": {
        "summary": "loaded data health",
        "capability": "data_health",
        "needs_subject": False,
    },
    "note_evidence": {
        "summary": "retrieved note/policy evidence",
        "capability": "hybrid_notes",
        "needs_subject": False,
    },
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


class ToolCallModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    subject: str | None = None


class AnalystLoopOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    tools: list[ToolCallModel] = []


def tools_for_capability(capability: str) -> tuple[str, ...]:
    return CAPABILITY_TOOLS.get(capability, ())


def _trace_entry(name: str, subject: str | None, *, ok: bool, detail: str) -> dict[str, Any]:
    spec = REGISTERED_TOOLS.get(name) or {}
    summary = spec.get("summary") or name
    if subject:
        summary = f"{summary} {subject}"
    return {
        "tool": name,
        "subject": subject,
        "ok": ok,
        "summary": summary,
        "detail": detail,
    }


def execute_registered_tool(
    con,
    name: str,
    *,
    subject: str | None = None,
    question: str = "",
    as_of: str | None = None,
) -> dict[str, Any]:
    spec = REGISTERED_TOOLS.get(name)
    if spec is None:
        return _trace_entry(name, subject, ok=False, detail="unknown tool")
    if spec["needs_subject"] and not subject:
        return _trace_entry(name, subject, ok=False, detail="subject required")
    capability = spec["capability"]
    try:
        bundle = assemble_context(
            con,
            question=question or f"{name} {subject or ''}".strip(),
            intent=capability,
            sku=subject,
            as_of=as_of,
        )
    except (KeyError, ValueError) as exc:
        return _trace_entry(name, subject, ok=False, detail=str(exc))
    n_obj = len(bundle.objects)
    return _trace_entry(
        name,
        subject,
        ok=True,
        detail=f"objects={n_obj} sufficient={bundle.sufficient}",
    )


def _followup_question(
    question: str,
    history: list[dict[str, Any]] | None,
) -> tuple[str, str | None]:
    """Modest continuity. Business facts are still re-resolved."""
    text = (question or "").strip()
    if not history:
        return text, None
    last = history[-1]
    last_subject = None
    plan = last.get("plan") or {}
    last_subject = plan.get("subject")
    objects = (last.get("bundle") or {}).get("objects") or []
    item_ids = [o.get("id") for o in objects if o.get("type") == "Item" and o.get("id")]
    lowered = text.lower()
    if lowered in {"why?", "why", "why is that?"}:
        if last_subject:
            return f"Why is {last_subject} on the attention queue?", last_subject
        recs = ((last.get("bundle") or {}).get("facts") or {}).get("attention") or {}
        rows = recs.get("recommendations") if isinstance(recs, dict) else None
        if isinstance(rows, list) and rows:
            sku = (rows[0] or {}).get("sku") or (rows[0] or {}).get("item_sku")
            if sku:
                return f"Why is {sku} on the attention queue?", str(sku)
        if item_ids:
            return f"Why is {item_ids[0]} on the attention queue?", item_ids[0]
        return text, last_subject
    if "second item" in lowered or "the second" in lowered:
        if len(item_ids) >= 2:
            return f"What is the state of {item_ids[1]}?", item_ids[1]
        recs = (
            ((last.get("bundle") or {}).get("facts") or {}).get("attention")
            or {}
        )
        rows = recs.get("recommendations") if isinstance(recs, dict) else None
        if isinstance(rows, list) and len(rows) >= 2:
            sku = (rows[1] or {}).get("sku") or (rows[1] or {}).get("item_sku")
            if sku:
                return f"What is the state of {sku}?", str(sku)
    if "last week" in lowered or "since last week" in lowered:
        return text, last_subject
    return text, last_subject


def _loop_prompt(question: str, traces: list[dict[str, Any]], remaining: int) -> str:
    import json

    return (
        "Select zero or more registered READ tools, or finish.\n"
        "Return JSON only: {\"action\": \"call\"|\"finish\", \"tools\": "
        "[{\"name\": \"...\", \"subject\": null}]}. No SQL. extra fields forbidden.\n"
        f"registered_tools: {sorted(REGISTERED_TOOLS)}\n"
        f"remaining_iterations: {remaining}\n"
        f"question: {question}\n"
        f"already_ran: {json.dumps(traces, default=str)}\n"
    )


def _parse_loop(raw: str) -> AnalystLoopOutput | None:
    import json

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        parsed = AnalystLoopOutput.model_validate(payload)
    except ValidationError:
        return None
    if parsed.action not in {"call", "finish"}:
        return None
    return parsed


def run_analyst(
    con,
    *,
    question: str,
    intent: str | None = None,
    sku: str | None = None,
    as_of: str | None = None,
    provider: LLMProvider | None = None,
    history: list[dict[str, Any]] | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> dict[str, Any]:
    used = provider or get_provider()
    resolved_q, follow_subject = _followup_question(question, history)
    subject = sku or follow_subject
    plan = plan_question(
        resolved_q, intent=intent, subject=subject, as_of=as_of, provider=used
    )
    traces: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    initial_tools = tools_for_capability(plan.capability)
    for name in initial_tools:
        key = (name, plan.subject)
        if key in seen:
            continue
        seen.add(key)
        traces.append(
            execute_registered_tool(
                con,
                name,
                subject=plan.subject,
                question=resolved_q,
                as_of=as_of or plan.as_of,
            )
        )

    iterations = 1
    if is_real_provider_name(used.name):
        while iterations < max_iterations:
            remaining = max_iterations - iterations
            try:
                raw = used.complete(_loop_prompt(resolved_q, traces, remaining))
            except Exception:
                break
            parsed = _parse_loop(raw)
            iterations += 1
            if parsed is None or parsed.action == "finish":
                break
            added = False
            for call in parsed.tools:
                if call.name not in REGISTERED_TOOLS:
                    traces.append(
                        _trace_entry(
                            call.name, call.subject, ok=False, detail="unknown tool"
                        )
                    )
                    continue
                key = (call.name, call.subject or plan.subject)
                if key in seen:
                    continue
                seen.add(key)
                traces.append(
                    execute_registered_tool(
                        con,
                        call.name,
                        subject=call.subject or plan.subject,
                        question=resolved_q,
                        as_of=as_of or plan.as_of,
                    )
                )
                added = True
            if not added:
                break

    bundle = assemble_context(
        con,
        question=resolved_q,
        intent=intent,
        sku=subject,
        as_of=as_of,
        plan=plan,
    )
    result = ground_from_bundle(
        bundle, plan=plan, provider=used, tool_trace=traces
    )
    result["question"] = question
    result["resolved_question"] = resolved_q
    result["iterations"] = iterations
    result["max_iterations"] = max_iterations
    kind = "fake"
    if used.name != "fake":
        from .gateway import load_model_config

        try:
            kind = load_model_config().kind
        except ValueError:
            kind = "remote"
        if getattr(used, "name", "") == "openai_compatible":
            base = getattr(used, "base_url", "") or ""
            if "localhost" in base or "127.0.0.1" in base:
                kind = "local"
            else:
                kind = "remote"
    result["provider_kind"] = kind
    result["real_model"] = used.name != "fake"
    return result


def plan_only(
    question: str,
    *,
    intent: str | None = None,
    subject: str | None = None,
    as_of: str | None = None,
    provider: LLMProvider | None = None,
) -> QuestionPlan:
    used = provider or get_provider()
    if intent:
        return deterministic_plan(
            question, intent=intent, subject=subject, as_of=as_of
        )
    return plan_question(
        question, intent=intent, subject=subject, as_of=as_of, provider=used
    )
