"""Source loaders. Order matters: dims before facts, items before events."""
from __future__ import annotations

from .base import IngestJob, recover_orphaned_runs
from .catalog import ChannelIngest, ItemEventIngest, ItemIngest
from .insights import ContentIngest, ContentSnapshotIngest
from .notes import NoteIngest
from .sales import EngagementIngest, ListingEventIngest, ListingIngest, OrderIngest

ALL_JOBS: list[type[IngestJob]] = [
    ChannelIngest,
    ItemIngest,
    ItemEventIngest,
    ListingIngest,
    ListingEventIngest,
    EngagementIngest,
    OrderIngest,
    ContentIngest,
    ContentSnapshotIngest,
    NoteIngest,
]

JOBS_BY_SOURCE: dict[str, type[IngestJob]] = {j.source: j for j in ALL_JOBS}

__all__ = ["ALL_JOBS", "JOBS_BY_SOURCE", "IngestJob", "recover_orphaned_runs"]
