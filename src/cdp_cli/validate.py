"""Pydantic models validating source JSONL before it touches the warehouse.

Every source stream gets a model. Rejected rows are quarantined with
reasons so upstream data issues are auditable, never silent.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ChannelRecord(BaseModel):
    platform: str
    handle: str
    standing: Literal["active", "suspended", "closed"] = "active"
    region: str | None = None
    fee_pct: float = Field(ge=0.0, le=1.0, default=0.0)
    valid_from: datetime


class ItemRecord(BaseModel):
    sku: str
    product: str
    variant: str | None = None
    size: str | None = None
    category: str | None = None
    condition: Literal["new", "like_new", "used", "worn"] | None = None
    acquisition_channel: str | None = None
    acquisition_cost_cny: float | None = Field(default=None, ge=0)
    qty: int = Field(default=1, ge=0)
    status: Literal["planned", "in_transit", "owned", "listed", "sold", "archived"] = "owned"
    target_price_usd: float | None = Field(default=None, ge=0)
    notes: str | None = None


class ItemEventRecord(BaseModel):
    item_sku: str
    event_type: Literal["ordered", "received", "listed", "price_change", "sold", "note"]
    event_at: datetime | None = None
    actor: str | None = None
    payload: dict[str, Any] | None = None


class ListingRecord(BaseModel):
    item_sku: str
    platform: str
    platform_url: str | None = None
    price_usd: float = Field(gt=0)
    status: Literal["draft", "active", "sold", "ended"] = "active"
    listed_at: datetime
    sold_at: datetime | None = None
    sold_price_usd: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def sold_implies_price(self):
        """Cross-field invariants run at model level — field validators
        see single fields in isolation in v2."""
        if self.status == "sold" and self.sold_price_usd is None:
            raise ValueError("sold listings must have sold_price_usd")
        return self


class EngagementRecord(BaseModel):
    listing_ref: str  # platform listing key or item sku
    platform: str
    snapshot_at: date
    views: int = Field(default=0, ge=0)
    watchers: int = Field(default=0, ge=0)
    offers: int = Field(default=0, ge=0)


class OrderRecord(BaseModel):
    order_id: str
    item_sku: str
    platform: str
    qty: int = Field(ge=1)
    price_usd: float = Field(gt=0)
    fees_usd: float = Field(default=0, ge=0)
    shipping_usd: float = Field(default=0, ge=0)
    status: Literal["shipped", "delivered", "returned", "cancelled"] = "shipped"
    order_at: datetime


class ContentRecord(BaseModel):
    content_id: str
    item_sku: str | None = None
    body: str = Field(min_length=1)
    tone: Literal["urgent", "storyteller", "minimal", "hype", "informative"]
    cta: str | None = None
    hooks: list[str] = Field(default_factory=list)
    status: Literal["draft", "published", "retired"] = "draft"
    published_at: datetime | None = None
    platform: str | None = None


class ContentEngagementRecord(BaseModel):
    content_id: str
    observed_at: datetime
    window_hours: int = Field(default=48, ge=1)
    impressions: int = Field(ge=0)
    saves: int = Field(default=0, ge=0)
    inquiries: int = Field(default=0, ge=0)
    conversions: int = Field(default=0, ge=0)


class PurchaseOrderRecord(BaseModel):
    order_id: str
    supplier: str
    currency: str = "CNY"
    expected_delivery: date | None = None
    status: Literal["draft", "ordered", "in_transit", "delivered", "partial"] = "ordered"
    total_cny: float = Field(ge=0)
    shipping_cny: float = Field(default=0, ge=0)
    lines: list[dict[str, Any]] = Field(min_length=1)
