"""Ingest reconciliation + warehouse trust signals.

Answers the operational questions:
- Did read = loaded + rejected for each recent run?
- Are there failed / orphaned / all-reject runs?
- Is the current warehouse state trustworthy enough to reason over?

Kept out of the CLI so the same logic powers `cdp status`, the API, and
(eventually) typed AI tools — one definition of "healthy."
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import duckdb


@dataclass(frozen=True)
class RunReconciliation:
    run_id: str
    source: str
    status: str
    rows_read: int
    rows_loaded: int
    rows_rejected: int
    balanced: bool  # read == loaded + rejected (only meaningful on success)
    all_rejected: bool
    started_at: Any
    error_message: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrustReport:
    """Warehouse trustworthiness snapshot."""

    ok: bool
    reasons: tuple[str, ...]
    orphaned_running: int
    failed_runs: int
    unbalanced_success_runs: int
    all_reject_success_runs: int
    total_rejected_records: int
    recent_runs: tuple[RunReconciliation, ...]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        d["recent_runs"] = [r.to_dict() for r in self.recent_runs]
        return d


def _int(v: Any) -> int:
    return int(v or 0)


def latest_runs(con: duckdb.DuckDBPyConnection, limit: int = 20) -> list[RunReconciliation]:
    rows = con.execute(
        """
        SELECT run_id, source, status,
               coalesce(rows_read, 0),
               coalesce(rows_loaded, 0),
               coalesce(rows_rejected, 0),
               started_at, error_message
        FROM core.ingest_runs
        ORDER BY started_at DESC NULLS LAST
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    out: list[RunReconciliation] = []
    for run_id, source, status, read, loaded, rejected, started, err in rows:
        read_i, loaded_i, rejected_i = _int(read), _int(loaded), _int(rejected)
        balanced = (status != "success") or (read_i == loaded_i + rejected_i)
        all_rejected = status == "success" and read_i > 0 and loaded_i == 0 and rejected_i == read_i
        out.append(
            RunReconciliation(
                run_id=run_id,
                source=source,
                status=status,
                rows_read=read_i,
                rows_loaded=loaded_i,
                rows_rejected=rejected_i,
                balanced=balanced,
                all_rejected=all_rejected,
                started_at=started,
                error_message=err,
            )
        )
    return out


def trust_report(con: duckdb.DuckDBPyConnection, recent_limit: int = 20) -> TrustReport:
    orphaned = _int(
        con.execute(
            "SELECT count(*) FROM core.ingest_runs WHERE status = 'running'"
        ).fetchone()[0]
    )
    failed = _int(
        con.execute(
            "SELECT count(*) FROM core.ingest_runs WHERE status = 'failed'"
        ).fetchone()[0]
    )
    rejected_total = _int(
        con.execute("SELECT count(*) FROM core.rejected_records").fetchone()[0]
    )

    recent = latest_runs(con, limit=recent_limit)

    # Full-history integrity scan (cheap at this scale).
    unbalanced_all = _int(
        con.execute(
            """
            SELECT count(*) FROM core.ingest_runs
            WHERE status = 'success'
              AND coalesce(rows_read, 0)
                  != coalesce(rows_loaded, 0) + coalesce(rows_rejected, 0)
            """
        ).fetchone()[0]
    )
    all_reject_all = _int(
        con.execute(
            """
            SELECT count(*) FROM core.ingest_runs
            WHERE status = 'success'
              AND coalesce(rows_read, 0) > 0
              AND coalesce(rows_loaded, 0) = 0
              AND coalesce(rows_rejected, 0) = coalesce(rows_read, 0)
            """
        ).fetchone()[0]
    )

    reasons: list[str] = []
    if orphaned:
        reasons.append(f"{orphaned} orphaned running run(s) — recover before trusting state")
    if failed:
        reasons.append(f"{failed} failed run(s) in audit history")
    if unbalanced_all:
        reasons.append(
            f"{unbalanced_all} success run(s) fail read=loaded+rejected reconciliation"
        )
    if all_reject_all:
        reasons.append(
            f"{all_reject_all} success run(s) loaded nothing (all rows rejected)"
        )

    # "ok" means no active integrity alarms. Failed historical runs alone do not
    # make the warehouse untrustworthy if they were rolled back; orphaned and
    # unbalanced successes do. All-reject is a warning, not a hard fail — the
    # pipeline did its job, but the operator must notice.
    hard_fail = orphaned > 0 or unbalanced_all > 0
    return TrustReport(
        ok=not hard_fail,
        reasons=tuple(reasons),
        orphaned_running=orphaned,
        failed_runs=failed,
        unbalanced_success_runs=unbalanced_all,
        all_reject_success_runs=all_reject_all,
        total_rejected_records=rejected_total,
        recent_runs=tuple(recent),
    )


def format_status(
    con: duckdb.DuckDBPyConnection,
    *,
    db_path_str: str,
    size_kb: float,
) -> str:
    """Human-readable `cdp status` body."""
    lines: list[str] = [f"db: {db_path_str} ({size_kb:.1f} KB)"]

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
        lines.append(f"  {label:18} {n}")

    trust = trust_report(con)
    lines.append("")
    lines.append(f"trust: {'OK' if trust.ok else 'ATTENTION NEEDED'}")
    if trust.reasons:
        for reason in trust.reasons:
            lines.append(f"  - {reason}")
    else:
        lines.append("  - no integrity alarms")

    lines.append("")
    lines.append("reconciliation (recent runs):")
    lines.append(
        f"  {'source':28} {'status':8} {'read':>5} {'load':>5} {'rej':>5} balanced"
    )
    if not trust.recent_runs:
        lines.append("  (no ingest runs yet)")
    for r in trust.recent_runs[:12]:
        bal = "yes" if r.balanced else "NO"
        if r.all_rejected:
            bal = "ALL-REJ"
        lines.append(
            f"  {r.source:28} {r.status:8} {r.rows_read:5} {r.rows_loaded:5} "
            f"{r.rows_rejected:5} {bal}"
        )
    return "\n".join(lines) + "\n"
