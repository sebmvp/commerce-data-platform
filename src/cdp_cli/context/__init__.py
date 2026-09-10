"""Context engine public surface.

Generic types and assembly live in cdp_cli.core. Resale intents remain
importable here so existing CLI/API/MCP callers do not change.
"""

from ..core.engine import assemble_context
from ..core.model import (
    ContextBundle,
    ContextEvent,
    ContextLink,
    ContextObject,
    MissingContext,
)
from ..domains.resale.intents import INTENTS, REQUIRED_CONCEPTS, extract_sku, resolve_intent

__all__ = [
    "INTENTS",
    "REQUIRED_CONCEPTS",
    "ContextBundle",
    "ContextEvent",
    "ContextLink",
    "ContextObject",
    "MissingContext",
    "assemble_context",
    "extract_sku",
    "resolve_intent",
]
