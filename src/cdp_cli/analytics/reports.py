"""Markdown report renderers — the artifacts a small operator actually reads.

Reports are deterministic renders of warehouse views; the same SQL is
available ad-hoc via `cdp query`, these just package the common questions.
"""
from __future__ import annotations

from datetime import datetime, timezone

import duckdb


def _md_table(cols: list[str], rows: list[tuple]) -> list[str]:
    lines = ["| " + " | ".join(cols) + " |",
             "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(
            f"{v:,.2f}" if isinstance(v, float) else str(v if v is not None else "—")
            for v in r) + " |")
    return lines or ["_no rows_"]


def _inventory(con: duckdb.DuckDBPyConnection) -> list[str]:
    out = ["## Inventory position", ""]
    out += _md_table(
        ["status", "items", "units", "invested_cny", "invested_usd_est", "listed"],
        con.execute("SELECT * FROM catalog.v_inventory_summary").fetchall())
    out += ["", "## Unlisted queue (owned, highest capital first)", ""]
    out += _md_table(
        ["sku", "product", "variant", "size", "condition", "cost_cny", "target_usd", "since"],
        con.execute("""
            SELECT sku, product, variant, size, condition,
                   acquisition_cost_cny, target_price_usd, date_trunc('day', updated_at)
            FROM catalog.v_unlisted_queue LIMIT 15""").fetchall())
    return out


def _pricing(con: duckdb.DuckDBPyConnection) -> list[str]:
    out = ["## Pricing lens — watch-rate vs. price position", "",
           "Listings where watchers accumulate but no sale: price is the likely friction.", ""]
    out += _md_table(
        ["sku", "product", "platform", "price_usd", "views", "watchers",
         "offers", "watch_rate", "status"],
        con.execute("""
            SELECT sku, product, platform, price_usd, views, watchers,
                   offers, watch_rate, listing_status
            FROM sales.v_listing_performance
            ORDER BY watch_rate DESC NULLS LAST LIMIT 20""").fetchall())
    return out


def _funnel(con: duckdb.DuckDBPyConnection) -> list[str]:
    out = ["## Funnel by channel", ""]
    out += _md_table(
        ["platform", "listings", "sold", "sell_through", "avg_days_to_sell", "gross_usd"],
        con.execute("SELECT * FROM sales.v_sell_through").fetchall())
    out += ["", "## Content effectiveness (published pieces)", ""]
    out += _md_table(
        ["tone", "cta", "pieces", "impressions", "saves", "inquiries",
         "conversions", "avg_er"],
        con.execute("SELECT * FROM insights.v_content_effectiveness").fetchall())
    out += ["", "## Current voice profiles", ""]
    out += _md_table(
        ["tone", "hook_style", "sample", "avg_watchers", "avg_conv", "version"],
        con.execute("""
            SELECT tone, hook_style, sample_size, avg_watchers,
                   avg_conversion, version
            FROM insights.voice_profile WHERE is_current
            ORDER BY avg_conversion DESC""").fetchall())
    return out


_RENDERERS = {"inventory": _inventory, "pricing": _pricing, "funnel": _funnel}


def render(con: duckdb.DuckDBPyConnection, kind: str) -> str:
    if kind not in _RENDERERS:
        raise ValueError(f"unknown report kind: {kind}")
    header = [
        f"# CDP report — {kind}",
        f"_generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} from warehouse views_",
        "",
    ]
    return "\n".join(header + _RENDERERS[kind](con)) + "\n"
