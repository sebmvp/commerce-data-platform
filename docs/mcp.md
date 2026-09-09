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
| `get_business_snapshot` | `business.py` |
| `get_inventory_attention_queue` | `business.py` |
| `get_ingest_health` | `business.py` |
| `explain_metric` | metric registry |
| `get_item` | `business.py` |
| `get_item_history` | `business.py` |
| `get_channel_as_of` | `business.py` |
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
