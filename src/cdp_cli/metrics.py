"""Compatibility re-export. Resale metric definitions live in the resale domain."""

from cdp_cli.domains.resale.metrics import (
    ATTENTION_QUEUE_DEFAULT_LIMIT,
    CNY_TO_USD_EST,
    HIGH_WATCH_RATE,
    METRICS,
    STALE_LISTING_DAYS,
    MetricDef,
    get_metric,
    metric_catalog,
)

__all__ = [
    "ATTENTION_QUEUE_DEFAULT_LIMIT",
    "CNY_TO_USD_EST",
    "HIGH_WATCH_RATE",
    "METRICS",
    "STALE_LISTING_DAYS",
    "MetricDef",
    "get_metric",
    "metric_catalog",
]
