"""Read-only tool bodies shared by the MCP server.

These call the same Python functions as CLI and FastAPI. They do not
open a second query path and they do not expose approve/execute.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .. import actions as act
from .. import db
from ..core import assemble_context
from ..domains.resale import services as biz
from ..domains.resale.metrics import metric_catalog

# Names an agent host might try. They are not registered and call_read_tool
# rejects them so a later copilot cannot approve through this adapter.
FORBIDDEN_TOOL_NAMES = frozenset({
    "approve_action",
    "reject_action",
    "execute_action",
    "propose_action",
})

READ_TOOL_NAMES = (
    "assemble_context",
    "get_business_snapshot",
    "get_inventory_attention_queue",
    "get_ingest_health",
    "explain_metric",
    "get_item",
    "get_item_history",
    "get_channel_as_of",
    "list_actions",
)


def _with_warehouse(fn: Callable[[Any], Any]) -> Any:
    if not db.is_initialized():
        raise FileNotFoundError("database not initialized (run: cdp build / make seed)")
    con = db.connect(read_only=True)
    try:
        return fn(con)
    finally:
        con.close()


def _assemble_context(
    *,
    question: str = "",
    intent: str | None = None,
    sku: str | None = None,
) -> dict[str, Any]:
    return _with_warehouse(
        lambda con: assemble_context(
            con, question=question or "", intent=intent, sku=sku
        ).to_dict()
    )


def _snapshot() -> dict[str, Any]:
    return _with_warehouse(lambda con: biz.get_business_snapshot(con).to_dict())


def _attention(*, limit: int = 25) -> dict[str, Any]:
    return _with_warehouse(
        lambda con: biz.get_inventory_attention_queue(con, limit=limit).to_dict()
    )


def _health() -> dict[str, Any]:
    return _with_warehouse(lambda con: biz.get_ingest_health(con).to_dict())


def _explain_metric(*, name: str | None = None) -> dict[str, Any]:
    if name:
        return biz.explain_metric(name).to_dict()
    return {
        "kind": "fact",
        "data": metric_catalog(),
        "provenance": {
            "tool": "metric_catalog",
            "source_relations": ["cdp_cli.domains.resale.metrics.METRICS"],
        },
    }


def _item(*, sku: str) -> dict[str, Any]:
    return _with_warehouse(lambda con: biz.get_item(con, sku).to_dict())


def _item_history(*, sku: str) -> dict[str, Any]:
    return _with_warehouse(lambda con: biz.get_item_history(con, sku).to_dict())


def _channel(
    *,
    platform: str,
    as_of: str | None = None,
    handle: str | None = None,
) -> dict[str, Any]:
    return _with_warehouse(
        lambda con: biz.get_channel_as_of(
            con, platform, as_of=as_of, handle=handle
        ).to_dict()
    )


def _list_actions(
    *,
    status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    return act.list_actions(status=status, limit=limit)


_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "assemble_context": _assemble_context,
    "get_business_snapshot": _snapshot,
    "get_inventory_attention_queue": _attention,
    "get_ingest_health": _health,
    "explain_metric": _explain_metric,
    "get_item": _item,
    "get_item_history": _item_history,
    "get_channel_as_of": _channel,
    "list_actions": _list_actions,
}


def call_read_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """Dispatch a read tool by name. Unknown and write tools raise ValueError."""
    if name in FORBIDDEN_TOOL_NAMES or name not in _HANDLERS:
        raise ValueError(f"unknown tool {name!r}")
    return _HANDLERS[name](**kwargs)
