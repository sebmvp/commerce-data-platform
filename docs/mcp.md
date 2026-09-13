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
| `assemble_context` | context engine |
| `get_business_snapshot` | `domains/resale/services` |
| `get_inventory_attention_queue` | `domains/resale/services` |
| `get_ingest_health` | `domains/resale/services` |
| `explain_metric` | `domains/resale/metrics` |
| `get_item` | `domains/resale/services` |
| `get_item_history` | `domains/resale/services` |
| `get_channel_as_of` | `domains/resale/services` |
| `list_actions` | sandbox log (read) |

Not registered: `propose_action`, `approve_action`, `reject_action`, `execute_action`.

If `assemble_context` returns `sufficient: false`, a copilot should abstain or qualify. The server does not invent missing listings or prices.

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
