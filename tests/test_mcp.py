"""MCP adapter — same services as FastAPI, no write/approve tools.

The engine already exists. This slice only exposes it to agents.
"""
from __future__ import annotations

import asyncio

import pytest

from cdp_cli import db
from cdp_cli.context import assemble_context
from cdp_cli.ingest import ALL_JOBS
from cdp_cli.mcp.tools import FORBIDDEN_TOOL_NAMES, READ_TOOL_NAMES, call_read_tool


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_read_surface_excludes_human_gated_writes():
    assert "assemble_context" in READ_TOOL_NAMES
    assert "get_item" in READ_TOOL_NAMES
    for name in (
        "approve_action",
        "reject_action",
        "execute_action",
        "propose_action",
    ):
        assert name in FORBIDDEN_TOOL_NAMES
        assert name not in READ_TOOL_NAMES


def test_assemble_context_tool_matches_engine(warehouse):
    _build(warehouse)
    warehouse.close()
    via_tool = call_read_tool(
        "assemble_context",
        question="Should I reprice stone-cargo-l?",
        intent="reprice_item",
        sku="stone-cargo-l",
    )
    con = db.connect(read_only=True)
    try:
        via_engine = assemble_context(
            con,
            question="Should I reprice stone-cargo-l?",
            intent="reprice_item",
            sku="stone-cargo-l",
        ).to_dict()
    finally:
        con.close()

    assert via_tool["intent"] == "reprice_item"
    assert via_tool["sufficient"] is False
    concepts = {row["concept"] for row in via_tool["missing_context"]}
    assert "listing" in concepts
    assert via_tool["provenance"]["tool"] == "assemble_context"
    assert via_tool["intent"] == via_engine["intent"]
    assert via_tool["sufficient"] == via_engine["sufficient"]
    assert via_tool["missing_context"] == via_engine["missing_context"]


def test_focus_today_tool_is_sufficient(warehouse):
    _build(warehouse)
    warehouse.close()
    payload = call_read_tool("assemble_context", intent="focus_today")
    assert payload["intent"] == "focus_today"
    assert payload["sufficient"] is True
    assert "snapshot" in payload["facts"]


def test_get_item_tool_is_the_business_payload(warehouse):
    _build(warehouse)
    warehouse.close()
    payload = call_read_tool("get_item", sku="stone-cargo-l")
    assert payload["kind"] == "fact"
    assert payload["data"]["item"]["sku"] == "stone-cargo-l"
    assert payload["provenance"]["tool"] == "get_item"


def test_unknown_sku_is_not_invented(warehouse):
    _build(warehouse)
    warehouse.close()
    with pytest.raises(KeyError):
        call_read_tool("get_item", sku="no-such-sku")


def test_unknown_tool_is_rejected():
    with pytest.raises(ValueError, match="unknown tool"):
        call_read_tool("approve_action", action_id="x")


def test_mcp_server_lists_only_read_tools(warehouse):
    pytest.importorskip("mcp")
    _build(warehouse)
    warehouse.close()
    from mcp import Client

    from cdp_cli.mcp.server import create_server

    async def _run():
        async with Client(create_server()) as client:
            listed = await client.list_tools()
            tools = listed.tools if hasattr(listed, "tools") else listed
            names = {t.name for t in tools}
            assert names == set(READ_TOOL_NAMES)
            assert names.isdisjoint(FORBIDDEN_TOOL_NAMES)

    asyncio.run(_run())


def test_mcp_assemble_context_over_protocol(warehouse):
    pytest.importorskip("mcp")
    _build(warehouse)
    warehouse.close()
    from mcp import Client

    from cdp_cli.mcp.server import create_server

    async def _run():
        async with Client(create_server()) as client:
            result = await client.call_tool(
                "assemble_context",
                {
                    "question": "Should I reprice stone-cargo-l?",
                    "intent": "reprice_item",
                    "sku": "stone-cargo-l",
                },
            )
            assert result.is_error is False
            body = result.structured_content
            assert body["sufficient"] is False
            concepts = {row["concept"] for row in body["missing_context"]}
            assert "listing" in concepts

    asyncio.run(_run())
