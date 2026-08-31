"""Analytics views return consistent numbers after a build."""
from __future__ import annotations

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS


def _build(con):
    for j in ALL_JOBS:
        j(con, db.data_dir()).run()


def test_inventory_summary(warehouse):
    _build(warehouse)
    rows = warehouse.execute(
        "SELECT status, items FROM catalog.v_inventory_summary").fetchall()
    total = sum(r[1] for r in rows)
    assert total == 12


def test_listing_performance_aggregates(warehouse):
    _build(warehouse)
    rows = warehouse.execute(
        "SELECT views, watchers, offers, watch_rate "
        "FROM sales.v_listing_performance WHERE listing_status='sold'"
    ).fetchall()
    assert len(rows) > 0
    for views, watchers, offers, rate in rows:
        assert views > 0
        assert rate is None or rate >= 0


def test_sell_through_grouped(warehouse):
    _build(warehouse)
    platforms = warehouse.execute(
        "SELECT platform, listings, sold FROM sales.v_sell_through").fetchall()
    assert {r[0] for r in platforms} <= {"grailed", "depop"}


def test_reports_render(warehouse):
    _build(warehouse)
    from cdp_cli.analytics import reports
    md = reports.render(warehouse, "inventory")
    assert "## Inventory position" in md
    assert "Unlisted queue" in md
