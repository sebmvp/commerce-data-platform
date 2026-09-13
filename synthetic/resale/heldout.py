#!/usr/bin/env python3
"""World B — held-out synthetic resale world.

Different seed, identifiers, and dates from the demo world. Same domain
rules. No copied SKUs. Used for held-out scenario validation, not gold
tuning.

Usage: python scripts/generate_heldout_world.py
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20260615
NOW = datetime(2026, 6, 15, 12, 0, 0)
OUT = Path(__file__).resolve().parents[2] / "sample_data_heldout"

random.seed(SEED)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat(timespec="seconds")


def _w(name: str, rows: list[dict]) -> None:
    path = OUT / name
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str) + "\n")
    print(f"  {name}: {len(rows)}")


def _item(**kw) -> dict:
    base = {
        "variant": None,
        "size": None,
        "category": "catalog.sneakers",
        "condition": "used",
        "acquisition_channel": "wholesale",
        "qty": 1,
        "notes": "synthetic held-out fixture",
        "target_price_usd": None,
        "acquisition_cost_cny": None,
    }
    base.update(kw)
    return base


def _events_for(sku: str, ordered: datetime, received: datetime | None,
                listed: datetime | None, sold: datetime | None,
                price: float | None = None) -> list[dict]:
    out = [{"item_sku": sku, "event_type": "ordered", "event_at": _iso(ordered),
            "actor": "batchimport", "payload": {"supplier": "cnx440"}}]
    if received:
        out.append({"item_sku": sku, "event_type": "received", "event_at": _iso(received),
                    "actor": "batchimport", "payload": {}})
    if listed:
        out.append({"item_sku": sku, "event_type": "listed", "event_at": _iso(listed),
                    "payload": {"price_usd": price}})
    if sold:
        out.append({"item_sku": sku, "event_type": "sold", "event_at": _iso(sold),
                    "payload": {}})
    return out


def _eng(sku: str, platform: str, start: datetime, days: int, *,
         views_base: int, watch_frac: float, offer_frac: float) -> list[dict]:
    rows = []
    for d in range(1, days + 1):
        day_gain = max(2, int(views_base * (0.9 ** d) * random.uniform(0.7, 1.2)))
        rows.append({
            "listing_ref": sku,
            "platform": platform,
            "snapshot_at": (start + timedelta(days=d)).date().isoformat(),
            "views": day_gain,
            "watchers": max(0, int(day_gain * watch_frac)),
            "offers": max(0, int(day_gain * offer_frac)),
        })
    return rows


def generate() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    channels = [
        {"platform": "grailed", "handle": "atelier.north", "standing": "active",
         "region": "US", "fee_pct": 0.08, "valid_from": "2025-02-01T00:00:00"},
        {"platform": "grailed", "handle": "atelier.north", "standing": "active",
         "region": "US", "fee_pct": 0.11, "valid_from": "2026-02-01T00:00:00"},
        {"platform": "depop", "handle": "ateliernorth", "standing": "active",
         "region": "US", "fee_pct": 0.10, "valid_from": "2026-01-10T00:00:00"},
    ]

    items: list[dict] = []
    events: list[dict] = []
    listings: list[dict] = []
    listing_events: list[dict] = []
    engagement: list[dict] = []
    orders: list[dict] = []
    notes: list[dict] = []

    def add_listing(sku, platform, price, listed_at, status="active",
                    sold_at=None, sold_price=None, price_history=None):
        listings.append({
            "item_sku": sku, "platform": platform,
            "platform_url": f"https://{platform}.example/{sku}",
            "price_usd": round(price, 2), "status": status,
            "listed_at": _iso(listed_at),
            "sold_at": _iso(sold_at),
            "sold_price_usd": None if sold_price is None else round(sold_price, 2),
        })
        history = price_history or [(listed_at, price, "opened", "active")]
        for at, px, etype, st in history:
            listing_events.append({
                "item_sku": sku, "platform": platform, "event_type": etype,
                "event_at": _iso(at), "price_usd": round(px, 2), "status": st,
            })
        if sold_at and not any(e["event_type"] == "sold" and e["item_sku"] == sku
                               and e["platform"] == platform for e in listing_events):
            listing_events.append({
                "item_sku": sku, "platform": platform, "event_type": "sold",
                "event_at": _iso(sold_at), "price_usd": sold_price, "status": "sold",
            })

    listed = NOW - timedelta(days=40)
    reprice = NOW - timedelta(days=18)
    items.append(_item(
        sku="merino-crew-m", product="Merino Crewneck — Charcoal",
        variant="charcoal", size="M", category="catalog.tops", condition="like_new",
        acquisition_channel="retail", acquisition_cost_cny=980,
        status="listed", target_price_usd=145.0,
        notes="synthetic held-out: merino crew",
    ))
    events += _events_for("merino-crew-m", listed - timedelta(days=16),
                          listed - timedelta(days=10), listed, None, 145.0)
    events.append({"item_sku": "merino-crew-m", "event_type": "price_change",
                   "event_at": _iso(reprice), "payload": {"price_usd": 129.0}})
    add_listing("merino-crew-m", "grailed", 129.0, listed, price_history=[
        (listed, 145.0, "opened", "active"),
        (reprice, 129.0, "price_change", "active"),
    ])
    engagement += _eng("merino-crew-m", "grailed", listed, 10, views_base=55,
                       watch_frac=0.11, offer_frac=0.02)
    notes.append({
        "note_id": "note-merino-pill", "kind": "seller_note",
        "object_type": "item", "object_id": "merino-crew-m",
        "title": "Pilling at cuffs",
        "body": "Held-out note: light cuff pilling. Photograph in daylight, do not call it new.",
    })

    items.append(_item(
        sku="cord-blazer-s", product="Corduroy Blazer — Moss",
        variant="moss", size="S", category="catalog.outerwear", condition="new",
        acquisition_cost_cny=2100, status="owned", target_price_usd=240.0,
        notes="synthetic held-out: unlisted blazer",
    ))
    events += _events_for("cord-blazer-s", NOW - timedelta(days=33),
                          NOW - timedelta(days=26), None, None)
    notes.append({
        "note_id": "note-blazer-fit", "kind": "seller_note",
        "object_type": "item", "object_id": "cord-blazer-s",
        "title": "Measurements pending",
        "body": "Still unlisted. Need chest and sleeve measurements before the listing goes up.",
    })

    j_list = NOW - timedelta(days=50)
    j_sold = j_list + timedelta(days=9)
    items.append(_item(
        sku="selvedge-jean-32", product="Selvedge Denim — Straight 32",
        size="32", category="catalog.bottoms", condition="used",
        acquisition_channel="retail", acquisition_cost_cny=720,
        status="sold", target_price_usd=110.0,
    ))
    events += _events_for("selvedge-jean-32", j_list - timedelta(days=11),
                          j_list - timedelta(days=6), j_list, j_sold, 110.0)
    add_listing("selvedge-jean-32", "grailed", 110.0, j_list, status="sold",
                sold_at=j_sold, sold_price=102.0)
    engagement += _eng("selvedge-jean-32", "grailed", j_list, 8, views_base=40,
                       watch_frac=0.1, offer_frac=0.04)
    orders.append({
        "order_id": "ord-selvedge-jean-32", "item_sku": "selvedge-jean-32",
        "platform": "grailed", "qty": 1, "price_usd": 102.0, "fees_usd": 12.24,
        "shipping_usd": 10.0, "status": "delivered", "order_at": _iso(j_sold),
    })

    t_list = NOW - timedelta(days=15)
    items.append(_item(
        sku="wax-trench-m", product="Waxed Cotton Trench — Olive",
        size="M", category="catalog.outerwear", condition="like_new",
        acquisition_channel="private", acquisition_cost_cny=1650,
        status="listed", target_price_usd=220.0,
    ))
    events += _events_for("wax-trench-m", t_list - timedelta(days=12),
                          t_list - timedelta(days=7), t_list, None, 220.0)
    add_listing("wax-trench-m", "grailed", 220.0, t_list)
    engagement += _eng("wax-trench-m", "grailed", t_list, 8, views_base=35,
                       watch_frac=0.14, offer_frac=0.01)

    for sku, product, cat, cost, tgt, size in [
        ("nylon-shorts-l", "Nylon Trail Shorts", "catalog.bottoms", 420, 75.0, "L"),
        ("chrome-belt-os", "Chrome Hardware Belt", "catalog.accessories", 280, 55.0, "OS"),
    ]:
        items.append(_item(sku=sku, product=product, size=size, category=cat,
                           acquisition_cost_cny=cost, status="owned",
                           target_price_usd=tgt, condition="new"))
        events += _events_for(sku, NOW - timedelta(days=24), NOW - timedelta(days=18), None, None)

    items.append(_item(sku="src-derby-9", product="Suede Derby — Dark Brown",
                       size="9", category="catalog.sneakers", status="in_transit",
                       acquisition_cost_cny=880, target_price_usd=130.0, condition="new"))
    events += _events_for("src-derby-9", NOW - timedelta(days=6), None, None, None)

    items.append(_item(sku="src-overshirt-m", product="Cotton Overshirt — Indigo",
                       size="M", category="catalog.tops", status="in_transit",
                       acquisition_cost_cny=640, target_price_usd=95.0))
    events += _events_for("src-overshirt-m", NOW - timedelta(days=4), None, None, None)

    items.append(_item(sku="recv-chore-m", product="Chore Coat — Khaki",
                       size="M", category="catalog.outerwear", status="owned",
                       acquisition_cost_cny=1100, target_price_usd=160.0, condition="new"))
    events += _events_for("recv-chore-m", NOW - timedelta(days=19),
                          NOW - timedelta(days=13), None, None)

    fresh = NOW - timedelta(days=2)
    items.append(_item(sku="fresh-slides-10", product="Leather Slide — Black",
                       size="10", category="catalog.sneakers", status="listed",
                       acquisition_cost_cny=360, target_price_usd=70.0, condition="new"))
    events += _events_for("fresh-slides-10", NOW - timedelta(days=11),
                          NOW - timedelta(days=6), fresh, None, 70.0)
    add_listing("fresh-slides-10", "depop", 70.0, fresh)
    engagement += _eng("fresh-slides-10", "depop", fresh, 2, views_base=22,
                       watch_frac=0.09, offer_frac=0.0)

    stale_at = NOW - timedelta(days=27)
    items.append(_item(sku="canvas-tote-os", product="Canvas Tote — Natural",
                       size="OS", category="catalog.accessories", status="listed",
                       acquisition_cost_cny=210, target_price_usd=48.0, condition="like_new"))
    events += _events_for("canvas-tote-os", stale_at - timedelta(days=10),
                          stale_at - timedelta(days=5), stale_at, None, 48.0)
    add_listing("canvas-tote-os", "grailed", 48.0, stale_at)
    engagement += _eng("canvas-tote-os", "grailed", stale_at, 9, views_base=18,
                       watch_frac=0.05, offer_frac=0.0)

    hv = NOW - timedelta(days=12)
    items.append(_item(sku="hopsack-trouser-34", product="Hopsack Trouser — Navy",
                       size="34", category="catalog.bottoms", status="listed",
                       acquisition_cost_cny=540, target_price_usd=90.0))
    events += _events_for("hopsack-trouser-34", hv - timedelta(days=9),
                          hv - timedelta(days=5), hv, None, 90.0)
    add_listing("hopsack-trouser-34", "grailed", 90.0, hv)
    engagement += _eng("hopsack-trouser-34", "grailed", hv, 8, views_base=160,
                       watch_frac=0.02, offer_frac=0.0)

    hw = NOW - timedelta(days=11)
    items.append(_item(sku="suede-loafer-9", product="Suede Loafer — Tobacco",
                       size="9", category="catalog.sneakers", status="listed",
                       acquisition_cost_cny=1250, target_price_usd=175.0, condition="like_new"))
    events += _events_for("suede-loafer-9", hw - timedelta(days=9),
                          hw - timedelta(days=4), hw, None, 175.0)
    add_listing("suede-loafer-9", "grailed", 175.0, hw)
    engagement += _eng("suede-loafer-9", "grailed", hw, 8, views_base=80,
                       watch_frac=0.22, offer_frac=0.0)

    of = NOW - timedelta(days=8)
    items.append(_item(sku="boiled-wool-s", product="Boiled Wool Cardigan",
                       size="S", category="catalog.tops", status="listed",
                       acquisition_cost_cny=760, target_price_usd=120.0, condition="new"))
    events += _events_for("boiled-wool-s", of - timedelta(days=8),
                          of - timedelta(days=4), of, None, 120.0)
    add_listing("boiled-wool-s", "depop", 120.0, of)
    engagement += _eng("boiled-wool-s", "depop", of, 7, views_base=60,
                       watch_frac=0.12, offer_frac=0.08)

    fs_list = NOW - timedelta(days=22)
    fs_sold = fs_list + timedelta(days=2)
    items.append(_item(sku="linen-shirt-m", product="Linen Camp Shirt — Sand",
                       size="M", category="catalog.tops", status="sold",
                       acquisition_cost_cny=390, target_price_usd=68.0, condition="used"))
    events += _events_for("linen-shirt-m", fs_list - timedelta(days=8),
                          fs_list - timedelta(days=4), fs_list, fs_sold, 68.0)
    add_listing("linen-shirt-m", "grailed", 68.0, fs_list, status="sold",
                sold_at=fs_sold, sold_price=64.0)
    engagement += _eng("linen-shirt-m", "grailed", fs_list, 2, views_base=90,
                       watch_frac=0.16, offer_frac=0.07)
    orders.append({
        "order_id": "ord-linen-shirt", "item_sku": "linen-shirt-m", "platform": "grailed",
        "qty": 1, "price_usd": 64.0, "fees_usd": 7.68, "shipping_usd": 9.0,
        "status": "shipped", "order_at": _iso(fs_sold),
    })

    ss_list = NOW - timedelta(days=52)
    ss_sold = ss_list + timedelta(days=36)
    items.append(_item(sku="field-jacket-l", product="Cotton Field Jacket — Stone",
                       size="L", category="catalog.outerwear", status="sold",
                       acquisition_cost_cny=980, target_price_usd=140.0))
    events += _events_for("field-jacket-l", ss_list - timedelta(days=10),
                          ss_list - timedelta(days=5), ss_list, ss_sold, 140.0)
    add_listing("field-jacket-l", "depop", 140.0, ss_list, status="sold",
                sold_at=ss_sold, sold_price=118.0)
    engagement += _eng("field-jacket-l", "depop", ss_list, 9, views_base=16,
                       watch_frac=0.05, offer_frac=0.02)
    orders.append({
        "order_id": "ord-field-jacket", "item_sku": "field-jacket-l", "platform": "depop",
        "qty": 1, "price_usd": 118.0, "fees_usd": 11.8, "shipping_usd": 8.0,
        "status": "delivered", "order_at": _iso(ss_sold),
    })

    rp_list = NOW - timedelta(days=38)
    rp_cut = rp_list + timedelta(days=11)
    rp_sold = rp_cut + timedelta(days=5)
    items.append(_item(sku="camp-cap-os", product="Cotton Camp Cap — Olive",
                       size="OS", category="catalog.accessories", status="sold",
                       acquisition_cost_cny=180, target_price_usd=42.0))
    events += _events_for("camp-cap-os", rp_list - timedelta(days=9),
                          rp_list - timedelta(days=4), rp_list, rp_sold, 42.0)
    events.append({"item_sku": "camp-cap-os", "event_type": "price_change",
                   "event_at": _iso(rp_cut), "payload": {"price_usd": 34.0}})
    add_listing("camp-cap-os", "grailed", 34.0, rp_list, status="sold",
                sold_at=rp_sold, sold_price=34.0, price_history=[
                    (rp_list, 42.0, "opened", "active"),
                    (rp_cut, 34.0, "price_change", "active"),
                    (rp_sold, 34.0, "sold", "sold"),
                ])
    engagement += _eng("camp-cap-os", "grailed", rp_list, 8, views_base=28,
                       watch_frac=0.09, offer_frac=0.03)
    orders.append({
        "order_id": "ord-camp-cap", "item_sku": "camp-cap-os", "platform": "grailed",
        "qty": 1, "price_usd": 34.0, "fees_usd": 4.08, "shipping_usd": 6.0,
        "status": "shipped", "order_at": _iso(rp_sold),
    })

    ml_list = NOW - timedelta(days=23)
    ml_p1 = ml_list + timedelta(days=7)
    ml_p2 = ml_list + timedelta(days=15)
    items.append(_item(sku="rugby-shirt-l", product="Stripe Rugby Shirt",
                       size="L", category="catalog.tops", status="listed",
                       acquisition_cost_cny=510, target_price_usd=85.0))
    events += _events_for("rugby-shirt-l", ml_list - timedelta(days=9),
                          ml_list - timedelta(days=4), ml_list, None, 85.0)
    add_listing("rugby-shirt-l", "grailed", 72.0, ml_list, price_history=[
        (ml_list, 85.0, "opened", "active"),
        (ml_p1, 78.0, "price_change", "active"),
        (ml_p2, 72.0, "price_change", "active"),
    ])
    engagement += _eng("rugby-shirt-l", "grailed", ml_list, 9, views_base=30,
                       watch_frac=0.08, offer_frac=0.01)

    du = NOW - timedelta(days=14)
    items.append(_item(sku="dual-duffel-os", product="Weekender Duffel — Navy",
                       size="OS", category="catalog.accessories", status="listed",
                       acquisition_cost_cny=890, target_price_usd=150.0, condition="new"))
    events += _events_for("dual-duffel-os", du - timedelta(days=11),
                          du - timedelta(days=6), du, None, 150.0)
    add_listing("dual-duffel-os", "grailed", 150.0, du)
    add_listing("dual-duffel-os", "depop", 138.0, du + timedelta(days=1))
    engagement += _eng("dual-duffel-os", "grailed", du, 7, views_base=40,
                       watch_frac=0.1, offer_frac=0.02)
    engagement += _eng("dual-duffel-os", "depop", du + timedelta(days=1), 6,
                       views_base=24, watch_frac=0.07, offer_frac=0.03)

    me = NOW - timedelta(days=6)
    items.append(_item(sku="miss-eng-scarf-os", product="Wool Scarf — Grey",
                       size="OS", category="catalog.accessories", status="listed",
                       acquisition_cost_cny=240, target_price_usd=55.0, condition="new"))
    events += _events_for("miss-eng-scarf-os", me - timedelta(days=9),
                          me - timedelta(days=4), me, None, 55.0)
    add_listing("miss-eng-scarf-os", "grailed", 55.0, me)

    items.append(_item(sku="miss-cost-pouch-os", product="Unlabeled Leather Pouch",
                       size="OS", category="catalog.accessories", status="owned",
                       acquisition_cost_cny=None, target_price_usd=40.0, condition="used"))
    events += _events_for("miss-cost-pouch-os", NOW - timedelta(days=14),
                          NOW - timedelta(days=9), None, None)

    g2_list = NOW - timedelta(days=44)
    g2_sold = g2_list + timedelta(days=12)
    items.append(_item(sku="sold-watch-cap-os", product="Watch Cap — Navy",
                       size="OS", category="catalog.accessories", status="sold",
                       acquisition_cost_cny=150, target_price_usd=32.0))
    events += _events_for("sold-watch-cap-os", g2_list - timedelta(days=7),
                          g2_list - timedelta(days=3), g2_list, g2_sold, 32.0)
    add_listing("sold-watch-cap-os", "grailed", 32.0, g2_list, status="sold",
                sold_at=g2_sold, sold_price=28.0)
    engagement += _eng("sold-watch-cap-os", "grailed", g2_list, 7, views_base=25,
                       watch_frac=0.1, offer_frac=0.03)
    orders.append({
        "order_id": "ord-watch-cap", "item_sku": "sold-watch-cap-os", "platform": "grailed",
        "qty": 1, "price_usd": 28.0, "fees_usd": 3.36, "shipping_usd": 5.0,
        "status": "delivered", "order_at": _iso(g2_sold),
    })

    filler = [
        ("hb-owned-01", "Poplin Shirt — White", "catalog.tops", "owned", 310, 58),
        ("hb-owned-02", "Drawstring Trouser", "catalog.bottoms", "owned", 470, 80),
        ("hb-owned-03", "Shetland Sweater", "catalog.tops", "owned", 620, 95),
        ("hb-owned-04", "Suede Belt — Tan", "catalog.accessories", "owned", 190, 45),
        ("hb-owned-05", "Cotton Oxford — Blue", "catalog.tops", "owned", 280, 52),
        ("hb-listed-01", "Trail Runner — Grey", "catalog.sneakers", "listed", 740, 120),
        ("hb-listed-02", "Denim Jacket — Wash", "catalog.outerwear", "listed", 880, 140),
        ("hb-listed-03", "Silk Scarf — Print", "catalog.accessories", "listed", 260, 60),
        ("hb-listed-04", "Chino — Stone 33", "catalog.bottoms", "listed", 390, 70),
        ("hb-listed-05", "Fleece Zip — Black", "catalog.tops", "listed", 430, 75),
        ("hb-listed-06", "Boat Shoe — Brown", "catalog.sneakers", "listed", 510, 88),
        ("hb-sold-01", "Cashmere Beanie", "catalog.accessories", "sold", 220, 48),
        ("hb-sold-02", "Poplin Short — Khaki", "catalog.bottoms", "sold", 250, 50),
        ("hb-sold-03", "Linen Overshirt", "catalog.tops", "sold", 560, 92),
        ("hb-transit-01", "Moleskin Jacket", "catalog.outerwear", "in_transit", 990, 155),
        ("hb-transit-02", "Crepe Sole Loafer", "catalog.sneakers", "in_transit", 870, 135),
        ("hb-owned-06", "Work Shirt — Hickory", "catalog.tops", "owned", 340, 62),
        ("hb-owned-07", "Wool Trouser — Grey", "catalog.bottoms", "owned", 710, 110),
        ("hb-listed-07", "Canvas Sneaker — White", "catalog.sneakers", "listed", 280, 55),
        ("hb-listed-08", "Rain Hat — Olive", "catalog.accessories", "listed", 160, 38),
        ("hb-owned-08", "Henley — Oat", "catalog.tops", "owned", 210, 42),
        ("hb-sold-04", "Depop tee filler", "catalog.tops", "sold", 90, 22),
        ("hb-owned-09", "Pleated Short — Navy", "catalog.bottoms", "owned", 330, 58),
        ("hb-listed-09", "Suede Chukka — Snuff", "catalog.sneakers", "listed", 1180, 165),
        ("hb-owned-10", "Alpaca Crew — Cream", "catalog.tops", "owned", 840, 125),
        ("hb-sold-05", "Cotton Bandana", "catalog.accessories", "sold", 40, 16),
    ]
    for i, (sku, product, cat, status, cost, tgt) in enumerate(filler):
        size = ["S", "M", "L", "8", "9", "OS"][i % 6]
        items.append(_item(sku=sku, product=product, size=size, category=cat,
                           acquisition_cost_cny=cost, status=status,
                           target_price_usd=float(tgt),
                           condition=random.choice(["new", "like_new", "used"])))
        ordered = NOW - timedelta(days=12 + (i % 18))
        received = None if status == "in_transit" else ordered + timedelta(days=5)
        listed_at = None
        sold_at = None
        if status in ("listed", "sold"):
            listed_at = received + timedelta(days=3 + (i % 4)) if received else None
        if status == "sold" and listed_at:
            sold_at = listed_at + timedelta(days=4 + (i % 10))
        events += _events_for(sku, ordered, received, listed_at, sold_at, float(tgt))
        if listed_at:
            platform = "depop" if sku.endswith("04") or "Depop" in product else (
                "depop" if i % 4 == 0 else "grailed"
            )
            st = "sold" if status == "sold" else "active"
            add_listing(sku, platform, float(tgt), listed_at, status=st,
                        sold_at=sold_at, sold_price=(float(tgt) * 0.9 if sold_at else None))
            if i % 5 != 0:
                engagement += _eng(sku, platform, listed_at, min(8, 3 + i % 5),
                                   views_base=16 + i * 2, watch_frac=0.07,
                                   offer_frac=0.02 if status == "sold" else 0.01)
            if sold_at:
                orders.append({
                    "order_id": f"ord-{sku}", "item_sku": sku, "platform": platform,
                    "qty": 1, "price_usd": round(float(tgt) * 0.9, 2),
                    "fees_usd": round(float(tgt) * 0.1, 2), "shipping_usd": 8.0,
                    "status": "shipped", "order_at": _iso(sold_at),
                })

    notes.extend([
        {"note_id": "policy-grailed-fees-heldout", "kind": "policy", "object_type": "channel",
         "object_id": "grailed", "title": "Grailed seller fee (held-out)",
         "body": "Held-out policy excerpt: Grailed seller fees are versioned on the channel. Do not invent a current fee."},
        {"note_id": "playbook-stale-listing-heldout", "kind": "playbook", "object_type": None,
         "object_id": None, "title": "Stale listing playbook",
         "body": "If an active listing is older than 14 days with no sale, review price and channel before cutting. High watch rate with zero offers is a price-friction signal."},
        {"note_id": "note-loafer-price", "kind": "seller_note", "object_type": "item",
         "object_id": "suede-loafer-9", "title": "Watchers without offers",
         "body": "Tobacco loafers are saved often with no offers. Ask is probably above recent comps."},
    ])

    _w("channels.jsonl", channels)
    _w("catalog_items.jsonl", items)
    _w("item_events.jsonl", sorted(events, key=lambda e: e["event_at"] or ""))
    _w("listings.jsonl", listings)
    _w("listing_events.jsonl", listing_events)
    _w("engagement_metrics.jsonl", engagement)
    _w("orders.jsonl", orders)
    _w("notes.jsonl", notes)
    meta = {
        "name": "heldout",
        "as_of": _iso(NOW),
        "seed": SEED,
        "purpose": "held-out scenario validation",
        "item_count": len(items),
        "calibration": (
            "Same domain rules as the demo world. Different seed, identifiers, "
            "and dates. Not a copy of the gold fixture."
        ),
    }
    (OUT / "world.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"heldout items={len(items)} listings={len(listings)} orders={len(orders)}")


if __name__ == "__main__":
    generate()
