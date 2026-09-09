#!/usr/bin/env python3
"""cdp — Commerce Data Platform CLI.

Commands:
  init                  Create schema + views
  build [--sample]      Full rebuild: schema, validate+ingest canonical data
  ingest [source]       Ingest one source or all (idempotent)
  validate              Dry-run validation report (no writes)
  query "SQL"           Ad-hoc SQL
  report <kind>         inventory | pricing | funnel  -> markdown export
  status                Health snapshot + ingest reconciliation
  business <topic>      snapshot | attention | health | metric | item | history | channel
  context               assemble a typed context bundle (objects/links/missing)
  demo                  3-minute warehouse → decision → failure story
  action                propose | list | get | approve | reject  (sandbox)
  tables                Row counts per table
  serve [--port N]      FastAPI read layer (requires cdp_cli[api])
  mcp                   MCP stdio server (requires cdp_cli[mcp])
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import db
from .ingest import ALL_JOBS, JOBS_BY_SOURCE


def _print_table(cols: list[str], rows: list[tuple]) -> None:
    print("\t".join(cols))
    for r in rows:
        print("\t".join("" if v is None else str(v) for v in r))
    if not rows:
        print("(no rows)", file=sys.stderr)


# ── commands ──────────────────────────────────────────────────────────────

def cmd_init(_: argparse.Namespace) -> int:
    db.ensure_database()
    con = db.connect()
    db.init_schema(con)
    con.close()
    print(f"Initialized schema + views in {db.database_url()}")
    return 0


def _run_ingest(con, sources: list[str], force: bool) -> int:
    from .ingest.base import recover_orphaned_runs

    # Clear any leftover 'running' audits before new work starts so status
    # and reconciliation never confuse a killed process with live work.
    recovered = recover_orphaned_runs(con)
    if recovered:
        print(f"  recovered {recovered} orphaned running ingest run(s) → failed")

    data = db.data_dir()
    rc = 0
    for source in sources:
        job = JOBS_BY_SOURCE[source](con, data)
        result = job.run(force=force)
        if result.get("skipped"):
            print(f"  {source:32} unchanged (skipped)")
        else:
            mark = "ok " if result["status"] == "success" else "ERR"
            print(f"  [{mark}] {source:28} read={result.get('read', 0):3} "
                  f"loaded={result.get('loaded', 0):3} rejected={result.get('rejected', 0):3}")
            if result["status"] != "success":
                rc = 1
    return rc


def cmd_ingest(args: argparse.Namespace) -> int:
    con = db.connect()
    try:
        sources = list(JOBS_BY_SOURCE) if args.source == "all" else [args.source]
        return _run_ingest(con, sources, force=args.force)
    finally:
        con.close()


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate every source file without writing — catches upstream breakage
    in CI before it ever reaches the warehouse."""
    from pydantic import ValidationError

    data = db.data_dir()
    total_read = total_bad = 0
    for job_cls in ALL_JOBS:
        path = data / job_cls.filename
        if not path.exists():
            print(f"  {job_cls.source:32} missing file: {path}")
            return 1
        read = bad = 0
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            read += 1
            try:
                job_cls.model.model_validate(json.loads(line))
            except ValidationError as ve:
                bad += 1
                if args.verbose:
                    first = ve.errors()[0]
                    print(f"    reject {job_cls.source}: "
                          f"{'.'.join(map(str, first['loc']))}: {first['msg']}")
        mark = "ok " if bad == 0 else "BAD"
        print(f"  [{mark}] {job_cls.source:28} {read:3} rows, {bad} rejected")
        total_read += read
        total_bad += bad
    print(f"\n{total_read} rows validated, {total_bad} rejected")
    return 0 if total_bad == 0 else 1


def cmd_build(args: argparse.Namespace) -> int:
    db.ensure_database()
    con = db.connect()
    try:
        db.init_schema(con)
        print(f"Schema initialized: {db.db_path()}")
        rc = _run_ingest(con, list(JOBS_BY_SOURCE), force=args.force)
        if rc == 0:
            from .analytics import aggregate
            n = aggregate.refresh_voice_profiles(con)
            print(f"Refreshed {n} voice profile version(s)")
            print("Build complete.")
        return rc
    finally:
        con.close()


def cmd_query(args: argparse.Namespace) -> int:
    con = db.connect(read_only=True)
    try:
        rel = con.execute(args.sql)
        _print_table([c[0] for c in rel.description], rel.fetchall())
        return 0
    finally:
        con.close()


def cmd_tables(_: argparse.Namespace) -> int:
    con = db.connect(read_only=True)
    try:
        _print_table(["schema", "table", "rows"], db.table_counts(con))
        return 0
    finally:
        con.close()


def cmd_status(_: argparse.Namespace) -> int:
    if not db.ping():
        print(f"database not reachable — run: make up (expected {db.database_url()})")
        return 1
    if not db.is_initialized():
        print(f"schema not initialized — run: cdp build (expected {db.database_url()})")
        return 1
    con = db.connect(read_only=True)
    try:
        from .observability import format_status, trust_report

        body = format_status(
            con,
            db_path_str=db.database_url(),
            size_kb=0.0,
        )
        print(body, end="")
        return 0 if trust_report(con).ok else 2
    finally:
        con.close()


def cmd_business(args: argparse.Namespace) -> int:
    """Operational decision surface — structured facts with provenance."""
    from . import business as biz
    from . import metrics as metrics_mod

    topic = args.topic
    as_json = args.json

    # explain_metric / catalog do not need the warehouse
    if topic == "metric":
        name = args.metric_name
        if not name:
            payload = {
                "kind": "fact",
                "data": metrics_mod.metric_catalog(),
                "provenance": {
                    "tool": "metric_catalog",
                    "source_relations": ["cdp_cli.metrics.METRICS"],
                },
            }
            _print_business(payload, as_json=as_json)
            return 0
        try:
            payload = biz.explain_metric(name).to_dict()
        except KeyError as e:
            print(str(e), file=sys.stderr)
            return 1
        _print_business(payload, as_json=as_json)
        return 0

    if not db.is_initialized():
        print(f"schema not initialized — run: cdp build (expected {db.database_url()})")
        return 1

    con = db.connect(read_only=True)
    try:
        if topic == "snapshot":
            payload = biz.get_business_snapshot(con).to_dict()
        elif topic == "attention":
            payload = biz.get_inventory_attention_queue(
                con, limit=args.limit
            ).to_dict()
        elif topic == "health":
            payload = biz.get_ingest_health(con).to_dict()
        elif topic in {"item", "history"}:
            sku = args.metric_name
            if not sku:
                print("sku required: cdp business item <sku>", file=sys.stderr)
                return 1
            try:
                if topic == "item":
                    payload = biz.get_item(con, sku).to_dict()
                else:
                    payload = biz.get_item_history(con, sku).to_dict()
            except KeyError as e:
                print(str(e), file=sys.stderr)
                return 1
        elif topic == "channel":
            platform = args.metric_name
            if not platform:
                print(
                    "platform required: cdp business channel <platform> [--as-of ISO]",
                    file=sys.stderr,
                )
                return 1
            try:
                payload = biz.get_channel_as_of(
                    con, platform, as_of=args.as_of, handle=args.handle
                ).to_dict()
            except KeyError as e:
                print(str(e), file=sys.stderr)
                return 1
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 1
        else:
            print(f"unknown business topic: {topic}", file=sys.stderr)
            return 1
        _print_business(payload, as_json=as_json)
        return 0
    finally:
        con.close()


def cmd_demo(_: argparse.Namespace) -> int:
    from .demo import run_demo

    return run_demo()


def cmd_action(args: argparse.Namespace) -> int:
    from . import actions as act
    from .present import format_action

    as_json = args.json
    try:
        if args.action_cmd == "propose":
            payload = act.propose(
                target_type=args.target_type,
                target_id=args.target_id,
                action_type=args.action_type,
                reason=args.reason,
                actor=args.actor,
            )
        elif args.action_cmd == "list":
            payload = act.list_actions(status=args.status, limit=args.limit)
        elif args.action_cmd == "get":
            payload = act.get_action(args.action_id)
        elif args.action_cmd == "approve":
            payload = act.approve_action(
                args.action_id, actor=args.actor, reason=args.reason
            )
        elif args.action_cmd == "reject":
            payload = act.reject_action(
                args.action_id, actor=args.actor, reason=args.reason
            )
        else:
            print(f"unknown action command: {args.action_cmd}", file=sys.stderr)
            return 1
    except (KeyError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return 0
    data = payload.get("data")
    if isinstance(data, dict) and "actions" in data:
        rows = data["actions"]
        if not rows:
            print("(no actions)")
            return 0
        for row in rows:
            print(format_action(row), end="")
        return 0
    if isinstance(data, dict):
        print(format_action(data), end="")
        return 0
    print(json.dumps(payload, indent=2, default=str))
    return 0


def _print_business(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
        return
    from .present import (
        format_attention,
        format_item,
        format_item_history,
        format_snapshot,
        format_trust,
    )

    data = payload.get("data")
    tool = (payload.get("provenance") or {}).get("tool")
    if tool == "get_business_snapshot" and isinstance(data, dict):
        print(format_snapshot(data), end="")
        return
    if tool == "get_inventory_attention_queue" and isinstance(data, dict):
        print(format_attention(data), end="")
        return
    if tool == "get_ingest_health" and isinstance(data, dict):
        print(format_trust(data), end="")
        return
    if tool == "get_item" and isinstance(data, dict):
        print(format_item(data), end="")
        return
    if tool == "get_item_history" and isinstance(data, dict):
        print(format_item_history(data), end="")
        return
    kind = payload.get("kind", "?")
    prov = payload.get("provenance") or {}
    print(f"kind: {kind}")
    if prov:
        print(f"tool: {prov.get('tool')}  as_of: {prov.get('as_of')}")
        if prov.get("metric_names"):
            print("metrics: " + ", ".join(prov["metric_names"]))
        for note in prov.get("notes") or []:
            print(f"  note: {note}")
    print("---")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "name" in item:
                print(f"  {item['name']:28} {item.get('unit', ''):6}  {item.get('definition', '')[:70]}")
            else:
                print(f"  {item}")
        return
    if isinstance(data, dict):
        for k, v in data.items():
            print(f"  {k:32} {v}")
        return
    print(data)


def cmd_context(args: argparse.Namespace) -> int:
    from .context import assemble_context
    from .present import format_context

    question = args.question or ""
    if not question.strip() and not args.intent:
        print("question or --intent is required", file=sys.stderr)
        return 1
    if not db.is_initialized():
        print(f"schema not initialized — run: cdp build (expected {db.database_url()})")
        return 1
    con = db.connect(read_only=True)
    try:
        bundle = assemble_context(
            con,
            question=question,
            intent=args.intent,
            sku=args.sku,
        )
    except (KeyError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        con.close()

    payload = bundle.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
        return 0
    print(format_context(payload), end="")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    from .analytics import reports

    con = db.connect(read_only=True)
    try:
        out_dir = db.project_root() / "reports"
        out_dir.mkdir(exist_ok=True)
        kind = args.kind
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = out_dir / f"{kind}_{ts}.md"
        path.write_text(reports.render(con, kind))
        print(f"wrote {path}")
        print(path.read_text())
        return 0
    finally:
        con.close()


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("API extra not installed. Run: pip install -e '.[api]'", file=sys.stderr)
        return 1
    from .api.main import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    import sys

    sys.path.insert(0, str(db.project_root()))
    from evals.run import run_eval

    if not db.is_initialized():
        print(f"schema not initialized — run: cdp build (expected {db.database_url()})")
        return 1
    con = db.connect(read_only=True)
    try:
        report = run_eval(con)
    finally:
        con.close()
    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0 if report["ok"] else 1
    print(
        f"TOTAL       {report['total']}\n"
        f"PASS        {report['passed']}\n"
        f"FAIL        {report['failed']}\n"
        f"SKIP        {report['skipped']}"
    )
    for case in report["cases"]:
        mark = "PASS" if case["passed"] else ("SKIP" if case["skipped"] else "FAIL")
        print(f"  [{mark}] {case['id']:4} {case['question']}")
        for err in case["errors"]:
            if err != "not implemented":
                print(f"         {err}")
    return 0 if report["ok"] else 1


def cmd_mcp(_: argparse.Namespace) -> int:
    """Stdio MCP server — agent adapter over the same tools as FastAPI."""
    try:
        from .mcp.server import create_server
    except ImportError:
        print("MCP extra not installed. Run: pip install -e '.[mcp]'", file=sys.stderr)
        return 1
    create_server().run()
    return 0


# ── parser ────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cdp", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="Create schema + views")

    pb = sub.add_parser("build", help="Full rebuild from canonical sources")
    pb.add_argument("--sample", action="store_true",
                    help="Explicitly acknowledge building from sample_data/")
    pb.add_argument("--force", action="store_true",
                    help="Re-ingest even files whose hashes match past runs")

    pi = sub.add_parser("ingest", help="Ingest data sources")
    pi.add_argument("source", nargs="?", default="all",
                    choices=["all", *JOBS_BY_SOURCE])
    pi.add_argument("--force", action="store_true")

    pv = sub.add_parser("validate", help="Dry-run source validation")
    pv.add_argument("-v", "--verbose", action="store_true")

    pq = sub.add_parser("query", help="Run ad-hoc SQL")
    pq.add_argument("sql")

    sub.add_parser("tables", help="Row counts per table")
    sub.add_parser("status", help="Health snapshot + ingest reconciliation")
    sub.add_parser("demo", help="Isolated warehouse story (does not touch CDP_DB)")

    pa = sub.add_parser("action", help="Sandbox operational actions (SQLite log)")
    a_sub = pa.add_subparsers(dest="action_cmd", required=True)

    def _json_flag(p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true")

    ap = a_sub.add_parser("propose", help="Record a proposed sandbox action")
    _json_flag(ap)
    ap.add_argument("--target-type", default="item", choices=["item", "listing"])
    ap.add_argument("--target-id", required=True, help="sku or listing_id")
    ap.add_argument(
        "--type",
        dest="action_type",
        required=True,
        choices=["propose_list", "propose_reprice", "propose_channel_change", "mark_reviewed"],
    )
    ap.add_argument("--reason", required=True)
    ap.add_argument("--actor", default="operator")
    al = a_sub.add_parser("list", help="List sandbox actions")
    _json_flag(al)
    al.add_argument("--status", choices=["proposed", "approved", "rejected"])
    al.add_argument("--limit", type=int, default=50)
    ag = a_sub.add_parser("get", help="Fetch one action")
    _json_flag(ag)
    ag.add_argument("action_id")
    aa = a_sub.add_parser("approve", help="Human-approve a proposed action")
    _json_flag(aa)
    aa.add_argument("action_id")
    aa.add_argument("--actor", default="operator")
    aa.add_argument("--reason", default=None)
    ar = a_sub.add_parser("reject", help="Human-reject a proposed action")
    _json_flag(ar)
    ar.add_argument("action_id")
    ar.add_argument("--actor", default="operator")
    ar.add_argument("--reason", default=None)

    pbiz = sub.add_parser(
        "business",
        help="Operational answers: snapshot | attention | health | metric | item | history | channel",
    )
    pbiz.add_argument(
        "topic",
        choices=["snapshot", "attention", "health", "metric", "item", "history", "channel"],
    )
    pbiz.add_argument(
        "metric_name",
        nargs="?",
        default=None,
        help="metric name, item sku, or channel platform depending on topic",
    )
    pbiz.add_argument(
        "--limit",
        type=int,
        default=25,
        help="attention queue size (default 25)",
    )
    pbiz.add_argument(
        "--as-of",
        dest="as_of",
        default=None,
        help="ISO-8601 timestamp for topic=channel (default: now)",
    )
    pbiz.add_argument(
        "--handle",
        default=None,
        help="channel handle filter (topic=channel)",
    )
    pbiz.add_argument(
        "--json",
        action="store_true",
        help="Emit structured payload (kind + data + provenance)",
    )

    from .context import INTENTS

    pc = sub.add_parser(
        "context",
        help="Assemble a typed context bundle for a business question",
    )
    pc.add_argument("question", nargs="?", default="", help="Question to ground")
    pc.add_argument("--intent", choices=sorted(INTENTS))
    pc.add_argument("--sku", default=None)
    pc.add_argument("--json", action="store_true")

    pr = sub.add_parser("report", help="Write a markdown report to reports/")
    pr.add_argument("kind", choices=["inventory", "pricing", "funnel"])

    pe = sub.add_parser("eval", help="Gold context-assembly evaluation")
    pe.add_argument("--json", action="store_true")
    pe.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Fail on FAIL or SKIP (default)",
    )

    ps = sub.add_parser("serve", help="FastAPI read layer")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8000)

    sub.add_parser("mcp", help="MCP stdio server (read tools only)")

    args = p.parse_args(argv)
    return {
        "init": cmd_init,
        "build": cmd_build,
        "ingest": cmd_ingest,
        "validate": cmd_validate,
        "query": cmd_query,
        "tables": cmd_tables,
        "status": cmd_status,
        "demo": cmd_demo,
        "action": cmd_action,
        "business": cmd_business,
        "context": cmd_context,
        "eval": cmd_eval,
        "report": cmd_report,
        "serve": cmd_serve,
        "mcp": cmd_mcp,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
