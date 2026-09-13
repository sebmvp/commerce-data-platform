"""Official MCP SDK adapter. No domain logic lives here."""
from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from .. import __version__
from .tools import call_read_tool

_READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)
# Real providers are not bit-identical across calls; FakeProvider is.
_ANSWER = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=False,
    open_world_hint=False,
)

_INSTRUCTIONS = """\
Read-only agent interface to the Commerce Data Platform context engine.

Prefer `answer` for operator questions. It is the same Analyst path as
POST /answer: plan, registered read tools, ContextBundle, fail-closed
grounding. If grounding_status is abstained, do not invent listings,
prices, or history. Use assemble_context when you need the typed bundle
without a model.

FACT / METRIC / RECOMMENDATION stay distinct in tool payloads.
Human approval gates actions. This server does not expose approve_action,
reject_action, execute_action, or propose_action. suggested_action in an
answer is a proposal, not a write.
"""


def _invoke(tool_name: str, **kwargs: Any) -> dict[str, Any]:
    try:
        return call_read_tool(tool_name, **kwargs)
    except (KeyError, ValueError, FileNotFoundError) as e:
        raise ToolError(str(e)) from e


def create_server() -> MCPServer:
    """Build an MCP server over the same services as FastAPI/CLI."""
    server = MCPServer(
        "commerce-data-platform",
        instructions=_INSTRUCTIONS,
        version=__version__,
        log_level="WARNING",
    )

    @server.tool(annotations=_READ_ONLY)
    def assemble_context(
        question: str = "",
        intent: str | None = None,
        sku: str | None = None,
    ) -> dict[str, Any]:
        """Assemble a typed ContextBundle for a bounded operational question."""
        return _invoke(
            "assemble_context", question=question, intent=intent, sku=sku
        )

    @server.tool(annotations=_ANSWER)
    def answer(
        question: str = "",
        intent: str | None = None,
        sku: str | None = None,
        as_of: str | None = None,
    ) -> dict[str, Any]:
        """Grounded Analyst answer over the same function as POST /answer."""
        return _invoke(
            "answer", question=question, intent=intent, sku=sku, as_of=as_of
        )

    @server.tool(annotations=_READ_ONLY)
    def get_business_snapshot() -> dict[str, Any]:
        """Current derived snapshot of inventory, capital, and trust."""
        return _invoke("get_business_snapshot")

    @server.tool(annotations=_READ_ONLY)
    def get_inventory_attention_queue(limit: int = 25) -> dict[str, Any]:
        """Ranked attention queue with reasons — a recommendation, not a fact."""
        return _invoke("get_inventory_attention_queue", limit=limit)

    @server.tool(annotations=_READ_ONLY)
    def get_ingest_health() -> dict[str, Any]:
        """Warehouse trust report (orphan runs, reconciliation)."""
        return _invoke("get_ingest_health")

    @server.tool(annotations=_READ_ONLY)
    def explain_metric(metric_name: str | None = None) -> dict[str, Any]:
        """Canonical metric definition, or the full catalog if metric_name is omitted."""
        return _invoke("explain_metric", name=metric_name)

    @server.tool(annotations=_READ_ONLY)
    def get_item(sku: str) -> dict[str, Any]:
        """Current item object plus listings and orders."""
        return _invoke("get_item", sku=sku)

    @server.tool(annotations=_READ_ONLY)
    def get_item_history(sku: str) -> dict[str, Any]:
        """Event timeline for one item."""
        return _invoke("get_item_history", sku=sku)

    @server.tool(annotations=_READ_ONLY)
    def get_channel_as_of(
        platform: str,
        as_of: str | None = None,
        handle: str | None = None,
    ) -> dict[str, Any]:
        """SCD-2 channel version covering as_of (ISO-8601, default now)."""
        return _invoke(
            "get_channel_as_of", platform=platform, as_of=as_of, handle=handle
        )

    @server.tool(annotations=_READ_ONLY)
    def list_actions(
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Read the sandbox action log. Does not approve or execute."""
        return _invoke("list_actions", status=status, limit=limit)

    return server
