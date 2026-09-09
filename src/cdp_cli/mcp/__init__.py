"""MCP adapter over the context engine.

`tools` has no SDK dependency. `server` requires extra `[mcp]`.
"""

from .tools import FORBIDDEN_TOOL_NAMES, READ_TOOL_NAMES, call_read_tool

__all__ = [
    "FORBIDDEN_TOOL_NAMES",
    "READ_TOOL_NAMES",
    "call_read_tool",
]
