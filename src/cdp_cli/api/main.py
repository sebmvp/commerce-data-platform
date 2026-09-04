"""FastAPI read layer.

Deliberately thin: the API *reads the warehouse views* — it does not own
business logic. Every endpoint maps 1:1 to a view or a constrained table
scan, so there is a single source of truth for metrics (the SQL itself).

Run: `cdp serve` then http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from .. import db


def _rows(con, sql: str, params: list | None = None) -> list[dict]:
    rel = con.execute(sql, params or [])
    cols = [c[0] for c in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Commerce Data Platform API",
        version="0.1.0",
        description="Read-only analytics surface over the CDP warehouse.",
    )

    @app.get("/health")
    def health():
        if not db.db_path().exists():
            raise HTTPException(503, "warehouse not built yet (run: cdp build)")
        con = db.connect(read_only=True)
        try:
            con.execute("SELECT 1")
            return {"status": "ok", "db": str(db.db_path())}
        finally:
            con.close()

    @app.get("/inventory/summary")
    def inventory_summary():
        con = db.connect(read_only=True)
        try:
            return _rows(con, "SELECT * FROM catalog.v_inventory_summary")
        finally:
            con.close()

    @app.get("/inventory/unlisted")
    def unlisted(limit: int = Query(50, le=200)):
        con = db.connect(read_only=True)
        try:
            return _rows(con,
                         "SELECT * FROM catalog.v_unlisted_queue LIMIT ?", [limit])
        finally:
            con.close()

    @app.get("/listings/performance")
    def listing_performance(platform: str | None = None):
        sql = "SELECT * FROM sales.v_listing_performance"
        params: list = []
        if platform:
            sql += " WHERE platform = ?"
            params.append(platform)
        sql += " ORDER BY watch_rate DESC NULLS LAST LIMIT 100"
        con = db.connect(read_only=True)
        try:
            return _rows(con, sql, params)
        finally:
            con.close()

    @app.get("/insights/voice-profiles")
    def voice_profiles():
        con = db.connect(read_only=True)
        try:
            return _rows(con, """
                SELECT tone, hook_style, sample_size, avg_watchers,
                       avg_conversion, summary_md, version
                FROM insights.voice_profile
                WHERE is_current ORDER BY avg_conversion DESC""")
        finally:
            con.close()

    @app.get("/ingest/runs")
    def ingest_runs(limit: int = Query(20, le=100)):
        con = db.connect(read_only=True)
        try:
            return _rows(con,
                         "SELECT * FROM core.v_ingest_health LIMIT ?", [limit])
        finally:
            con.close()

    @app.get("/ingest/trust")
    def ingest_trust():
        """Warehouse trustworthiness: reconciliation + orphan/failure alarms."""
        from ..observability import trust_report

        if not db.db_path().exists():
            raise HTTPException(503, "warehouse not built yet (run: cdp build)")
        con = db.connect(read_only=True)
        try:
            return trust_report(con).to_dict()
        finally:
            con.close()

    @app.get("/business/snapshot")
    def business_snapshot():
        from ..business import get_business_snapshot

        if not db.db_path().exists():
            raise HTTPException(503, "warehouse not built yet (run: cdp build)")
        con = db.connect(read_only=True)
        try:
            return get_business_snapshot(con).to_dict()
        finally:
            con.close()

    @app.get("/business/attention")
    def business_attention(limit: int = Query(25, le=200)):
        from ..business import get_inventory_attention_queue

        if not db.db_path().exists():
            raise HTTPException(503, "warehouse not built yet (run: cdp build)")
        con = db.connect(read_only=True)
        try:
            return get_inventory_attention_queue(con, limit=limit).to_dict()
        finally:
            con.close()

    @app.get("/business/metrics")
    def business_metrics(name: str | None = None):
        from ..business import explain_metric
        from ..metrics import metric_catalog

        if name:
            try:
                return explain_metric(name).to_dict()
            except KeyError as e:
                raise HTTPException(404, str(e)) from e
        return {"kind": "fact", "data": metric_catalog()}

    return app
