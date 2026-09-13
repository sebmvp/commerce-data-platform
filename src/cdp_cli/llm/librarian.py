"""Business Librarian: bounded read-only loop over registered domain tools.

The Librarian navigates modeled business context (objects, relationships,
history, metrics, rules, evidence, provenance) by calling tools the
active domain registered. It does not emit SQL, run Python, walk the
filesystem, or call the network. Business facts are always re-resolved
from the platform. Domain vocabulary lives on the Domain registration,
not here.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from ..core.domain import Domain, ReadToolSpec, get_active_domain
from ..core.engine import assemble_context
from ..core.plan import QuestionPlan
from .gateway import LLMProvider, get_provider, is_real_provider_name
from .grounding import ground_from_bundle
from .planner import deterministic_plan, plan_question

MAX_ITERATIONS = 4


class ToolCallModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    subject: str | None = None


class LibrarianLoopOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    tools: list[ToolCallModel] = []


def registered_tools(domain: Domain | None = None) -> dict[str, ReadToolSpec]:
    return (domain or get_active_domain()).read_tools


def tools_for_capability(capability: str, domain: Domain | None = None) -> tuple[str, ...]:
    return (domain or get_active_domain()).tools_for_capability(capability)


def _trace_entry(
    name: str,
    subject: str | None,
    *,
    ok: bool,
    detail: str,
    domain: Domain | None = None,
) -> dict[str, Any]:
    spec = registered_tools(domain).get(name)
    summary = spec.summary if spec is not None else name
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
    domain: Domain | None = None,
) -> dict[str, Any]:
    active = domain or get_active_domain()
    spec = active.read_tools.get(name)
    if spec is None:
        return _trace_entry(name, subject, ok=False, detail="unknown tool", domain=active)
    if spec.needs_subject and not subject:
        return _trace_entry(
            name, subject, ok=False, detail="subject required", domain=active
        )
    try:
        bundle = assemble_context(
            con,
            question=question or f"{name} {subject or ''}".strip(),
            intent=spec.capability,
            sku=subject,
            as_of=as_of,
            domain=active,
        )
    except (KeyError, ValueError) as exc:
        return _trace_entry(name, subject, ok=False, detail=str(exc), domain=active)
    n_obj = len(bundle.objects)
    return _trace_entry(
        name,
        subject,
        ok=True,
        detail=f"objects={n_obj} sufficient={bundle.sufficient}",
        domain=active,
    )


def _subject_ids(objects: list[dict[str, Any]], domain: Domain) -> list[str]:
    wanted = domain.entity_types[0] if domain.entity_types else None
    ids: list[str] = []
    for obj in objects:
        if wanted and obj.get("type") != wanted:
            continue
        ident = obj.get("id")
        if ident:
            ids.append(str(ident))
    return ids


def _followup_question(
    question: str,
    history: list[dict[str, Any]] | None,
    domain: Domain,
) -> tuple[str, str | None]:
    """Modest continuity. Business facts are still re-resolved."""
    text = (question or "").strip()
    if not history:
        return text, None
    last = history[-1]
    plan = last.get("plan") or {}
    last_subject = plan.get("subject")
    objects = (last.get("bundle") or {}).get("objects") or []
    ids = _subject_ids(objects, domain)
    lowered = text.lower()
    if lowered in {"why?", "why", "why is that?"}:
        if last_subject:
            return f"Why {last_subject}?", last_subject
        if ids:
            return f"Why {ids[0]}?", ids[0]
        return text, last_subject
    if "second" in lowered and len(ids) >= 2:
        return f"What is the state of {ids[1]}?", ids[1]
    return text, last_subject


def _loop_prompt(
    question: str,
    traces: list[dict[str, Any]],
    remaining: int,
    domain: Domain,
) -> str:
    import json

    names = sorted(domain.read_tools)
    return (
        "Select zero or more registered READ tools, or finish.\n"
        "Return JSON only: {\"action\": \"call\"|\"finish\", \"tools\": "
        "[{\"name\": \"...\", \"subject\": null}]}. No SQL. extra fields forbidden.\n"
        f"registered_tools: {names}\n"
        f"remaining_iterations: {remaining}\n"
        f"question: {question}\n"
        f"already_ran: {json.dumps(traces, default=str)}\n"
    )


def _parse_loop(raw: str) -> LibrarianLoopOutput | None:
    import json

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    try:
        parsed = LibrarianLoopOutput.model_validate(payload)
    except ValidationError:
        return None
    if parsed.action not in {"call", "finish"}:
        return None
    return parsed


def run_librarian(
    con,
    *,
    question: str,
    intent: str | None = None,
    sku: str | None = None,
    as_of: str | None = None,
    provider: LLMProvider | None = None,
    history: list[dict[str, Any]] | None = None,
    max_iterations: int = MAX_ITERATIONS,
    domain: Domain | None = None,
) -> dict[str, Any]:
    active = domain or get_active_domain()
    used = provider or get_provider()
    resolved_q, follow_subject = _followup_question(question, history, active)
    subject = sku or follow_subject
    plan = plan_question(
        resolved_q,
        intent=intent,
        subject=subject,
        as_of=as_of,
        provider=used,
        domain=active,
    )
    traces: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    initial_tools = tools_for_capability(plan.capability, active)
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
                domain=active,
            )
        )

    iterations = 1
    if is_real_provider_name(used.name):
        while iterations < max_iterations:
            remaining = max_iterations - iterations
            try:
                raw = used.complete(
                    _loop_prompt(resolved_q, traces, remaining, active)
                )
            except Exception:
                break
            parsed = _parse_loop(raw)
            iterations += 1
            if parsed is None or parsed.action == "finish":
                break
            added = False
            for call in parsed.tools:
                if call.name not in active.read_tools:
                    traces.append(
                        _trace_entry(
                            call.name,
                            call.subject,
                            ok=False,
                            detail="unknown tool",
                            domain=active,
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
                        domain=active,
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
        domain=active,
    )
    result = ground_from_bundle(
        bundle, plan=plan, provider=used, tool_trace=traces, domain=active
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
    domain: Domain | None = None,
) -> QuestionPlan:
    used = provider or get_provider()
    if intent:
        return deterministic_plan(
            question, intent=intent, subject=subject, as_of=as_of, domain=domain
        )
    return plan_question(
        question,
        intent=intent,
        subject=subject,
        as_of=as_of,
        provider=used,
        domain=domain,
    )
