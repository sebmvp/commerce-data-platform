"""FastAPI read layer.

Inventory/listing/insight routes read views. `/business/*`, `/context`,
`/eval`, and `/eval/compare` call shared services — same tools as the CLI and MCP.

Run: `cdp serve` then http://127.0.0.1:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .. import db


class ActionPropose(BaseModel):
    target_type: str = "item"
    target_id: str
    action_type: str
    reason: str
    actor: str = "operator"
    payload: dict | None = None
    recommendation_action: str | None = None


class ActionDecide(BaseModel):
    actor: str = "operator"
    reason: str | None = None


def _rows(con, sql: str, params: list | None = None) -> list[dict]:
    rel = con.execute(sql, params or [])
    cols = [c[0] for c in rel.description]
    return [dict(zip(cols, r)) for r in rel.fetchall()]


def _require_db() -> None:
    if not db.is_initialized():
        raise HTTPException(
            503, "database not initialized (run: cdp build / make seed)"
        )


def create_app() -> FastAPI:
    app = FastAPI(
        title="Commerce Data Platform API",
        version="0.6.0",
        description="Read layer over the context engine and operational store.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        _require_db()
        con = db.connect(read_only=True)
        try:
            con.execute("SELECT 1")
            return {"status": "ok", "db": db.database_url()}
        finally:
            con.close()

    @app.get("/inventory/summary")
    def inventory_summary():
        _require_db()
        con = db.connect(read_only=True)
        try:
            return _rows(con, "SELECT * FROM catalog.v_inventory_summary")
        finally:
            con.close()

    @app.get("/inventory/unlisted")
    def unlisted(limit: int = Query(50, le=200)):
        _require_db()
        con = db.connect(read_only=True)
        try:
            return _rows(
                con, "SELECT * FROM catalog.v_unlisted_queue LIMIT ?", [limit]
            )
        finally:
            con.close()

    @app.get("/listings/performance")
    def listing_performance(platform: str | None = None):
        _require_db()
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
        _require_db()
        con = db.connect(read_only=True)
        try:
            return _rows(
                con,
                """
                SELECT tone, hook_style, sample_size, avg_watchers,
                       avg_conversion, summary_md, version
                FROM insights.voice_profile
                WHERE is_current ORDER BY avg_conversion DESC
                """,
            )
        finally:
            con.close()

    @app.get("/ingest/runs")
    def ingest_runs(limit: int = Query(20, le=100)):
        _require_db()
        con = db.connect(read_only=True)
        try:
            return _rows(con, "SELECT * FROM core.v_ingest_health LIMIT ?", [limit])
        finally:
            con.close()

    @app.get("/ingest/trust")
    def ingest_trust():
        from ..observability import trust_report

        _require_db()
        con = db.connect(read_only=True)
        try:
            return trust_report(con).to_dict()
        finally:
            con.close()

    @app.get("/context")
    def context_bundle(
        question: str = Query(""),
        intent: str | None = Query(None),
        sku: str | None = Query(None),
    ):
        from ..context import assemble_context

        if not (question or "").strip() and not intent:
            raise HTTPException(400, "question or intent is required")
        _require_db()
        con = db.connect(read_only=True)
        try:
            return assemble_context(
                con, question=question, intent=intent, sku=sku
            ).to_dict()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        finally:
            con.close()

    @app.get("/answer")
    def grounded_answer(
        question: str = Query(""),
        intent: str | None = Query(None),
        sku: str | None = Query(None),
    ):
        from ..llm import ground_answer

        if not (question or "").strip() and not intent:
            raise HTTPException(400, "question or intent is required")
        _require_db()
        con = db.connect(read_only=True)
        try:
            return ground_answer(con, question=question, intent=intent, sku=sku)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        finally:
            con.close()

    @app.get("/eval")
    def eval_results():
        import sys

        from .. import db as _db

        sys.path.insert(0, str(_db.project_root()))
        from evals.run import run_eval

        _require_db()
        con = db.connect(read_only=True)
        try:
            return run_eval(con)
        finally:
            con.close()

    @app.get("/eval/compare")
    def eval_compare():
        import sys

        from .. import db as _db

        sys.path.insert(0, str(_db.project_root()))
        from evals.run import run_compare

        _require_db()
        con = db.connect(read_only=True)
        try:
            return run_compare(con)
        finally:
            con.close()

    @app.get("/business/snapshot")
    def business_snapshot():
        from ..business import get_business_snapshot

        _require_db()
        con = db.connect(read_only=True)
        try:
            return get_business_snapshot(con).to_dict()
        finally:
            con.close()

    @app.get("/business/attention")
    def business_attention(limit: int = Query(25, le=200)):
        from ..business import get_inventory_attention_queue

        _require_db()
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

    @app.get("/business/channels/{platform}")
    def business_channel(
        platform: str,
        as_of: str | None = Query(None),
        handle: str | None = Query(None),
    ):
        from ..business import get_channel_as_of

        _require_db()
        con = db.connect(read_only=True)
        try:
            return get_channel_as_of(
                con, platform, as_of=as_of, handle=handle
            ).to_dict()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        finally:
            con.close()

    @app.get("/business/items/{sku}")
    def business_item(sku: str):
        from ..business import get_item

        _require_db()
        con = db.connect(read_only=True)
        try:
            return get_item(con, sku).to_dict()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        finally:
            con.close()

    @app.get("/business/items/{sku}/history")
    def business_item_history(sku: str):
        from ..business import get_item_history

        _require_db()
        con = db.connect(read_only=True)
        try:
            return get_item_history(con, sku).to_dict()
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        finally:
            con.close()

    @app.post("/business/actions")
    def propose_action(body: ActionPropose):
        from .. import actions as act

        try:
            return act.propose(
                target_type=body.target_type,
                target_id=body.target_id,
                action_type=body.action_type,
                reason=body.reason,
                actor=body.actor,
                payload=body.payload,
                recommendation_action=body.recommendation_action,
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.get("/business/actions")
    def list_actions(status: str | None = Query(None), limit: int = Query(50, le=200)):
        from .. import actions as act

        try:
            return act.list_actions(status=status, limit=limit)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.get("/business/actions/{action_id}")
    def get_action(action_id: str):
        from .. import actions as act

        try:
            return act.get_action(action_id)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/business/actions/{action_id}/approve")
    def approve_action(action_id: str, body: ActionDecide | None = None):
        from .. import actions as act

        body = body or ActionDecide()
        try:
            return act.approve_action(
                action_id, actor=body.actor, reason=body.reason
            )
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/business/actions/{action_id}/reject")
    def reject_action(action_id: str, body: ActionDecide | None = None):
        from .. import actions as act

        body = body or ActionDecide()
        try:
            return act.reject_action(
                action_id, actor=body.actor, reason=body.reason
            )
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    return app
