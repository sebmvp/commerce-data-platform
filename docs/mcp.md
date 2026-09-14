# MCP (agent adapter)

Read-only tools over the same Python functions as CLI and FastAPI. No second query path. No approve/execute.

```bash
pip install -e ".[mcp]"
cdp mcp
```

stdio is the transport. A host (Claude Desktop, Cursor, Inspector) launches `cdp mcp` as a subprocess.

## Tools

| Tool | Source |
|---|---|
| `assemble_context` | context engine (`as_of` ISO-8601, same as GET `/context`) |
| `answer` | Business Librarian (`run_librarian`, same as POST `/answer`; optional `as_of`) |
| `get_business_snapshot` | `domains/resale/services` (omit `as_of` = live; pass ISO-8601 = reconstruct) |
| `get_inventory_attention_queue` | `domains/resale/services` |
| `get_ingest_health` | `domains/resale/services` |
| `explain_metric` | `domains/resale/metrics` |
| `get_item` | `domains/resale/services` |
| `get_item_history` | `domains/resale/services` |
| `get_channel_as_of` | `domains/resale/services` |
| `list_actions` | sandbox log (read) |

Not registered: `propose_action`, `approve_action`, `reject_action`, `execute_action`.

`answer` returns the Librarian payload: plan, tool trace, the exact bundle used, grounding_status, citations, and an optional suggested_action. That suggestion is not a write. `approve_action` is still not registered.

If `answer` returns `grounding_status: abstained`, or `assemble_context` returns `sufficient: false`, a copilot should abstain or qualify. The server does not invent missing listings or prices.

`as_of` is optional on `assemble_context`, `answer`, `get_business_snapshot`, and `get_channel_as_of`. Without it, relative phrases in the question still resolve against the world clock. With it, the host pins the instant the same way HTTP does.

Example host config:

```json
{
  "mcpServers": {
    "cdp": {
      "command": "cdp",
      "args": ["mcp"]
    }
  }
}
```

Point `CDP_DB` at a built warehouse. Tests use an in-memory MCP client (`tests/test_mcp.py`); they do not spawn this process.
