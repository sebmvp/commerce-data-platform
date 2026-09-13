"""Eval layers stay separate. No combined accuracy score."""
from __future__ import annotations

from cdp_cli import db
from cdp_cli.ingest import ALL_JOBS
from evals.analyst_eval import run_analyst_eval
from evals.plan_eval import run_plan_eval


def _build(con):
    for job in ALL_JOBS:
        job(con, db.data_dir()).run()


def test_plan_eval_layer(warehouse) -> None:
    _build(warehouse)
    report = run_plan_eval(warehouse)
    assert report["layer"] == "question_tool_planning"
    assert report["ok"] is True
    assert report["failed"] == 0
    assert "accuracy" not in report


def test_analyst_eval_layer(warehouse) -> None:
    _build(warehouse)
    report = run_analyst_eval(warehouse)
    assert report["layer"] == "agent_task_success"
    assert report["provider"] == "fake"
    assert report["ok"] is True
    assert report["failed"] == 0
