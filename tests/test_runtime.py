"""Runtime environment and source-coverage reports."""
from __future__ import annotations

from cdp_cli.completeness import source_completeness
from cdp_cli.runtime import runtime_info, world_kind


def test_world_kind_defaults_to_demo(monkeypatch, tmp_path):
    monkeypatch.delenv("CDP_WORLD", raising=False)
    monkeypatch.setenv("CDP_DATA", str(tmp_path))
    assert world_kind() == "demo"


def test_world_kind_heldout_from_dirname(monkeypatch, tmp_path):
    held = tmp_path / "sample_data_heldout"
    held.mkdir()
    monkeypatch.delenv("CDP_WORLD", raising=False)
    monkeypatch.setenv("CDP_DATA", str(held))
    assert world_kind() == "heldout"


def test_world_kind_private_from_env(monkeypatch):
    monkeypatch.setenv("CDP_WORLD", "private")
    assert world_kind() == "private"


def test_completeness_on_empty_warehouse(warehouse):
    report = source_completeness(warehouse)
    assert report["counts"]["items"] == 0
    assert report["counts"]["listings"] == 0
    assert "environment" in report


def test_runtime_info_redacts_password(monkeypatch):
    monkeypatch.setenv("CDP_WORLD", "demo")
    info = runtime_info()
    assert info["environment"] == "demo"
    assert info["synthetic"] is True
    assert info["model"]["provider"] == "fake"
    assert info["model"]["real"] is False
    db = str(info.get("database") or "")
    if ":" in db:
        assert "***" in db or "cdp" not in db.split("@")[0]
