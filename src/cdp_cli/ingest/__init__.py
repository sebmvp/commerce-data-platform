"""Source loaders. Order matters: dims before facts, items before events."""
from __future__ import annotations

from .base import IngestJob
from .catalog import ChannelIngest, ItemEventIngest, ItemIngest
from .insights import ContentIngest, ContentSnapshotIngest
from .sales import EngagementIngest, ListingIngest, OrderIngest

# Dependency-ordered: a later job may validate references against rows
# loaded by an earlier one.
ALL_JOBS: list[type[IngestJob]] = [
    ChannelIngest,
    ItemIngest,
    ItemEventIngest,
    ListingIngest,
    EngagementIngest,
    OrderIngest,
    ContentIngest,
    ContentSnapshotIngest,
]

JOBS_BY_SOURCE: dict[str, type[IngestJob]] = {j.source: j for j in ALL_JOBS}

__all__ = ["ALL_JOBS", "JOBS_BY_SOURCE", "IngestJob"]
