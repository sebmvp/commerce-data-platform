"""World clock must freeze relative phrases for synthetic evaluation."""
from __future__ import annotations

from datetime import datetime, timedelta

from cdp_cli.clock import reference_now, wall_now
from cdp_cli.domains.resale.intents import extract_as_of


def test_world_clock_is_demo_as_of(monkeypatch, tmp_path):
    world = tmp_path / "world.json"
    world.write_text('{"name": "demo", "as_of": "2026-09-09T12:00:00Z"}')
    monkeypatch.setenv("CDP_DATA", str(tmp_path))
    monkeypatch.delenv("CDP_AS_OF", raising=False)
    assert reference_now() == datetime.fromisoformat("2026-09-09T12:00:00")


def test_two_weeks_ago_uses_world_clock(monkeypatch, tmp_path):
    world = tmp_path / "world.json"
    world.write_text('{"as_of": "2026-09-09T12:00:00"}')
    monkeypatch.setenv("CDP_DATA", str(tmp_path))
    monkeypatch.delenv("CDP_AS_OF", raising=False)
    at = extract_as_of("What was the listing state two weeks ago?")
    assert at == datetime.fromisoformat("2026-09-09T12:00:00") - timedelta(days=14)


def test_explicit_wall_clock(monkeypatch):
    monkeypatch.setenv("CDP_AS_OF", "now")
    now = reference_now()
    assert abs((now - wall_now()).total_seconds()) < 5
