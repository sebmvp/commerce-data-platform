"""Explicit business metric definitions.

Every metric an operator or (later) AI tool may quote lives here with:
  - exact definition
  - grain
  - required fields
  - null behavior
  - temporal behavior

SQL views and Python tools must implement these definitions — not invent
parallel ones. If code and this module disagree, fix the code.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDef:
    name: str
    definition: str
    grain: str
    required_fields: tuple[str, ...]
    null_behavior: str
    temporal: str
    unit: str
    limitations: str = ""


# Default operational thresholds — named so they are not magic numbers
# scattered through SQL. Changing one is an explicit product decision.
STALE_LISTING_DAYS = 14
ATTENTION_QUEUE_DEFAULT_LIMIT = 25

# Approximate FX used only for *display* USD estimates of CNY cost basis.
# Not a treasury rate. Documented so nobody treats it as finance truth.
CNY_TO_USD_EST = 0.14


METRICS: dict[str, MetricDef] = {
    "inventory_cost_basis_cny": MetricDef(
        name="inventory_cost_basis_cny",
        definition=(
            "Sum of acquisition_cost_cny over items currently in status "
            "owned or listed (capital still tied up). Sold/archived excluded."
        ),
        grain="operation (groupable by status, category_key)",
        required_fields=("catalog.items.acquisition_cost_cny", "catalog.items.status"),
        null_behavior="NULL cost treated as 0 for sums; item still counted.",
        temporal="Point-in-time on current items projection.",
        unit="CNY",
        limitations="Does not include shipping, refurbishment, or holding cost.",
    ),
    "inventory_age_days": MetricDef(
        name="inventory_age_days",
        definition=(
            "Whole days from the item's acquisition anchor to as_of. "
            "Acquisition anchor = earliest item_event of type 'received', else "
            "'ordered', else items.created_at."
        ),
        grain="item",
        required_fields=("catalog.item_events.event_at", "catalog.items.created_at"),
        null_behavior="If no anchor can be resolved, NULL (never silently 0).",
        temporal="as_of parameter (default: current_timestamp).",
        unit="days",
    ),
    "listing_age_days": MetricDef(
        name="listing_age_days",
        definition="Whole days from listings.listed_at to as_of for active listings.",
        grain="listing",
        required_fields=("sales.listings.listed_at", "sales.listings.status"),
        null_behavior="NULL listed_at → NULL age.",
        temporal="as_of parameter (default: current_timestamp).",
        unit="days",
    ),
    "stale_listing": MetricDef(
        name="stale_listing",
        definition=(
            f"Active listing whose listing_age_days >= {STALE_LISTING_DAYS}."
        ),
        grain="listing",
        required_fields=("listing_age_days",),
        null_behavior="Unknown age → not stale (false), never guessed.",
        temporal=f"Threshold constant STALE_LISTING_DAYS={STALE_LISTING_DAYS}.",
        unit="boolean",
    ),
    "capital_tied_up_cny": MetricDef(
        name="capital_tied_up_cny",
        definition=(
            "Alias of inventory_cost_basis_cny restricted to unsold inventory "
            "(status in owned, listed). The operational 'what is stuck' number."
        ),
        grain="operation",
        required_fields=("inventory_cost_basis_cny",),
        null_behavior="Same as inventory_cost_basis_cny.",
        temporal="Point-in-time on current items projection.",
        unit="CNY",
    ),
    "unlisted_owned_count": MetricDef(
        name="unlisted_owned_count",
        definition="Count of items with status = 'owned' (acquired, not yet listed).",
        grain="operation",
        required_fields=("catalog.items.status",),
        null_behavior="N/A",
        temporal="Point-in-time.",
        unit="count",
    ),
    "watch_rate": MetricDef(
        name="watch_rate",
        definition="sum(watchers) / nullif(sum(views), 0) over engagement snapshots for a listing.",
        grain="listing",
        required_fields=("sales.engagement_metric.views", "sales.engagement_metric.watchers"),
        null_behavior="Zero views → NULL rate (not 0).",
        temporal="Across all snapshots currently loaded for the listing.",
        unit="ratio",
        limitations="Snapshots are not guaranteed daily-complete in all sources.",
    ),
    "sell_through_rate": MetricDef(
        name="sell_through_rate",
        definition="sold listings / all listings, grouped by channel platform.",
        grain="platform cohort",
        required_fields=("sales.listings.status", "core.channels.platform"),
        null_behavior="Empty cohort → NULL.",
        temporal="All listings currently in warehouse (not time-windowed yet).",
        unit="ratio",
        limitations="Not cohorted by list-date window; do not over-read as period sell-through.",
    ),
    "realized_revenue_usd": MetricDef(
        name="realized_revenue_usd",
        definition="Sum of sales.orders.revenue_usd for non-cancelled orders.",
        grain="operation (groupable by channel)",
        required_fields=("sales.orders.revenue_usd", "sales.orders.status"),
        null_behavior="NULL revenue treated as 0 for sums.",
        temporal="All orders currently loaded.",
        unit="USD",
    ),
    "realized_gross_after_fees_usd": MetricDef(
        name="realized_gross_after_fees_usd",
        definition=(
            "Sum of (revenue_usd - coalesce(fees_usd,0) - coalesce(shipping_usd,0)) "
            "for non-cancelled orders. NOT full margin: acquisition cost is separate."
        ),
        grain="operation",
        required_fields=("sales.orders.revenue_usd", "sales.orders.fees_usd", "sales.orders.shipping_usd"),
        null_behavior="Missing fees/shipping treated as 0.",
        temporal="All orders currently loaded.",
        unit="USD",
        limitations=(
            "Does not subtract acquisition cost or channel SCD fee_pct. "
            "Do not label this 'margin' in operator-facing output."
        ),
    ),
}


def get_metric(name: str) -> MetricDef:
    try:
        return METRICS[name]
    except KeyError as e:
        known = ", ".join(sorted(METRICS))
        raise KeyError(f"unknown metric {name!r}; known: {known}") from e


def metric_catalog() -> list[dict]:
    """Serializable catalog for CLI/API/AI explain_metric tools."""
    return [
        {
            "name": m.name,
            "definition": m.definition,
            "grain": m.grain,
            "required_fields": list(m.required_fields),
            "null_behavior": m.null_behavior,
            "temporal": m.temporal,
            "unit": m.unit,
            "limitations": m.limitations,
        }
        for m in METRICS.values()
    ]
