"""Interviewer demo: warehouse → business state → failure → still usable.

Does not modify committed sample_data/. Dirty input is staged in a temp copy.
Rebuilds the warehouse from sample_data so the run is deterministic.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from typing import TextIO

from . import business as biz
from . import db
from .ingest import JOBS_BY_SOURCE
from .ingest.catalog import ItemIngest
from .observability import trust_report
from .present import format_attention, format_rejects, format_snapshot, format_trust

DIRTY_LINES = (
    "{this is not json}\n",
    '{"sku": "demo-neg-cost", "product": "Invalid", "status": "owned", "acquisition_cost_cny": -1}\n',
)


def _banner(title: str, file: TextIO) -> None:
    print(file=file)
    print(title, file=file)
    print("-" * len(title), file=file)


def _count(con, sql: str) -> int:
    row = con.execute(sql).fetchone()
    return int(row[0]) if row else 0


def run_demo(*, file: TextIO = sys.stdout) -> int:
    data_dir = db.data_dir()
    catalog = data_dir / "catalog_items.jsonl"
    if not catalog.exists():
        print(f"missing sample data: {catalog}", file=sys.stderr)
        return 1

    path = db.db_path()
    if path.exists():
        path.unlink()
        print(f"rebuilding {path} from sample_data/", file=file)

    print("Commerce Data Platform — demo", file=file)
    print("synthetic data only · ~3 minutes", file=file)

    _banner("1. BUILD", file)
    con = db.connect()
    try:
        db.init_schema(con)
        print(f"schema: {path}", file=file)
        from .cli import _run_ingest

        rc = _run_ingest(con, list(JOBS_BY_SOURCE), False)
        if rc != 0:
            print("build failed", file=sys.stderr)
            return rc
        from .analytics import aggregate

        aggregate.refresh_voice_profiles(con)
        print("build complete.", file=file)

        _banner("2. BUSINESS STATE", file)
        snap = biz.get_business_snapshot(con)
        print(format_snapshot(snap.data), end="", file=file)

        _banner("3. ATTENTION", file)
        att = biz.get_inventory_attention_queue(con, limit=5)
        print(format_attention(att.data, limit=5), end="", file=file)

        _banner("4. FAILURE HANDLING", file)
        print("temp copy of catalog_items.jsonl + 2 bad lines", file=file)
        print("  - malformed JSON", file=file)
        print("  - schema violation (negative cost)", file=file)
        with tempfile.TemporaryDirectory(prefix="cdp-demo-") as tmp:
            dirty_dir = Path(tmp)
            shutil.copy(catalog, dirty_dir / "catalog_items.jsonl")
            with (dirty_dir / "catalog_items.jsonl").open("a") as fh:
                fh.writelines(DIRTY_LINES)
            result = ItemIngest(con, dirty_dir).run(force=True)
            print(
                f"  catalog.items  read={result.get('read')}  "
                f"loaded={result.get('loaded')}  rejected={result.get('rejected')}",
                file=file,
            )

        rejects = con.execute(
            """
            SELECT error_code, count(*), max(detail)
            FROM core.rejected_records
            GROUP BY 1
            ORDER BY 1
            """
        ).fetchall()
        print(file=file)
        print(format_rejects(rejects), end="", file=file)

        items_n = _count(con, "SELECT count(*) FROM catalog.items")
        print(
            f"  valid items still {items_n:,} "
            "(bad rows never entered catalog.items)",
            file=file,
        )

        _banner("5. TRUST AFTER FAILURE", file)
        health = biz.get_ingest_health(con)
        print(format_trust(health.data), end="", file=file)
        print("business state after the bad file:", file=file)
        print(format_snapshot(biz.get_business_snapshot(con).data), end="", file=file)

        _banner("6. REPLAY", file)
        print(
            "re-ingest sample_data/ — canonical files are unchanged, "
            "so content-hash skip fires",
            file=file,
        )
        _run_ingest(con, list(JOBS_BY_SOURCE), False)
        report = trust_report(con)
        items_n = _count(con, "SELECT count(*) FROM catalog.items")
        trust = "OK" if report.ok else "ATTENTION"
        print(
            f"  items={items_n}  rejected={report.total_rejected_records}  "
            f"trust={trust}",
            file=file,
        )
        print(file=file)
        print(
            "no duplicate catalog rows; quarantine from the dirty file remains.",
            file=file,
        )
        print(format_snapshot(biz.get_business_snapshot(con).data), end="", file=file)
        return 0 if report.ok else 2
    finally:
        con.close()
