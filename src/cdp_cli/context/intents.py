"""Compatibility shim. Resale intents live in cdp_cli.domains.resale."""

from ..domains.resale.intents import (
    INTENTS,
    ITEM_SCOPED,
    REQUIRED_CONCEPTS,
    extract_as_of,
    extract_sku,
    resolve_intent,
)

__all__ = [
    "INTENTS",
    "ITEM_SCOPED",
    "REQUIRED_CONCEPTS",
    "extract_as_of",
    "extract_sku",
    "resolve_intent",
]
