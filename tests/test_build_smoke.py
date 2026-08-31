"""End-to-end smoke test: full build from sample data loads every stream."""
from __future__ import annotations

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS


def test_full_build_loads_all_sources(warehouse):
    for job_cls in ALL_JOBS:
        result = job_cls(warehouse, db.data_dir()).run()
        assert result["status"] == "success", f"{result['source']} failed"
        assert result["rejected"] == 0, (
            f"{result['source']}: {result['rejected']} rejected unexpectedly")

    expected = {
        ("catalog", "items"): 12,
        ("catalog", "item_events"): 39,
        ("sales", "listings"): 9,
        ("sales", "orders"): 6,
        ("sales", "engagement_metric"): 71,
        ("insights", "content_pieces"): 9,
        ("insights", "content_snapshot"): 9,
        ("core", "channels"): 3,
    }
    for (schema, table), want in expected.items():
        (got,) = warehouse.execute(
            f'SELECT count(*) FROM "{schema}"."{table}"').fetchone()
        assert got == want, f"{schema}.{table}: expected {want}, got {got}"


def test_voice_profiles_derived(warehouse):
    for job_cls in ALL_JOBS:
        job_cls(warehouse, db.data_dir()).run()
    from cdp_cli.analytics.aggregate import refresh_voice_profiles
    n = refresh_voice_profiles(warehouse)
    assert n >= 1
    (current,) = warehouse.execute(
        "SELECT count(*) FROM insights.voice_profile WHERE is_current").fetchone()
    assert current >= 1
