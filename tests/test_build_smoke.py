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

    (items,) = warehouse.execute("SELECT count(*) FROM catalog.items").fetchone()
    assert 40 <= items <= 80
    (listings,) = warehouse.execute("SELECT count(*) FROM sales.listings").fetchone()
    assert listings >= 20
    (events,) = warehouse.execute("SELECT count(*) FROM sales.listing_events").fetchone()
    assert events >= 1
    (notes,) = warehouse.execute("SELECT count(*) FROM ops.notes").fetchone()
    assert notes >= 4
    (channels,) = warehouse.execute("SELECT count(*) FROM core.channels").fetchone()
    assert channels == 3


def test_voice_profiles_derived(warehouse):
    for job_cls in ALL_JOBS:
        job_cls(warehouse, db.data_dir()).run()
    from cdp_cli.analytics.aggregate import refresh_voice_profiles
    n = refresh_voice_profiles(warehouse)
    assert n >= 1
    (current,) = warehouse.execute(
        "SELECT count(*) FROM insights.voice_profile WHERE is_current").fetchone()
    assert current >= 1
