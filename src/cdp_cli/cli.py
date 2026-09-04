#!/usr/bin/env python3
"""cdp — Commerce Data Platform CLI.

Commands:
  init                  Create schema + views
  build [--sample]      Full rebuild: schema, validate+ingest canonical data
  ingest [source]       Ingest one source or all (idempotent)
  validate              Dry-run validation report (no writes)
  query "SQL"           Ad-hoc SQL
  report <kind>         inventory | pricing | funnel  -> markdown export
  status                Health snapshot
  tables                Row counts per table
  serve [--port N]      FastAPI read layer (requires cdp_cli[api])
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    con = db.connect()
    db.init_schema(con)
    con.close()
    print(f"Initialized schema + views in {db.db_path()}")
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
    path = db.db_path()
    if not path.exists():
        print(f"warehouse not initialized — run: cdp build (expected at {path})")
        return 1
    con = db.connect(read_only=True)
    try:
        print(f"db: {path} ({path.stat().st_size / 1024:.1f} KB)")
        checks = [
            ("items", "SELECT count(*) FROM catalog.items"),
            ("item_events", "SELECT count(*) FROM catalog.item_events"),
            ("listings", "SELECT count(*) FROM sales.listings"),
            ("orders", "SELECT count(*) FROM sales.orders"),
            ("engagement_snaps", "SELECT count(*) FROM sales.engagement_metric"),
            ("content_pieces", "SELECT count(*) FROM insights.content_pieces"),
            ("voice_profiles", "SELECT count(*) FROM insights.voice_profile WHERE is_current"),
            ("rejected_records", "SELECT count(*) FROM core.rejected_records"),
            ("ingest_runs", "SELECT count(*) FROM core.ingest_runs"),
        ]
        for label, q in checks:
            try:
                n = con.execute(q).fetchone()[0]
            except Exception:
                n = "?"
            print(f"  {label:18} {n}")
        return 0
    finally:
        con.close()


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
    sub.add_parser("status", help="Health snapshot")

    pr = sub.add_parser("report", help="Write a markdown report to reports/")
    pr.add_argument("kind", choices=["inventory", "pricing", "funnel"])

    ps = sub.add_parser("serve", help="FastAPI read layer")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8000)

    args = p.parse_args(argv)
    return {
        "init": cmd_init,
        "build": cmd_build,
        "ingest": cmd_ingest,
        "validate": cmd_validate,
        "query": cmd_query,
        "tables": cmd_tables,
        "status": cmd_status,
        "report": cmd_report,
        "serve": cmd_serve,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
