#!/usr/bin/env python3
"""Deterministic public synthetic resale world.

Calibrated from private lifecycle *patterns* (dual channel, unlisted capital,
sparse engagement, supply stages, notes-on-everything). No private identifiers.

Usage: python scripts/generate_public_world.py [--world demo|heldout|all]
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 20260909
NOW = datetime(2026, 9, 9, 12, 0, 0)
OUT = Path(__file__).resolve().parents[1] / "sample_data"

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
        "notes": "synthetic public fixture",
        "target_price_usd": None,
        "acquisition_cost_cny": None,
    }
    base.update(kw)
    return base


def _events_for(sku: str, ordered: datetime, received: datetime | None,
                listed: datetime | None, sold: datetime | None,
                price: float | None = None) -> list[dict]:
    out = [{"item_sku": sku, "event_type": "ordered", "event_at": _iso(ordered),
            "actor": "batchimport", "payload": {"supplier": "cnx433"}}]
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
        {"platform": "grailed", "handle": "_snkr.haus", "standing": "active",
         "region": "US", "fee_pct": 0.09, "valid_from": "2025-01-01T00:00:00"},
        {"platform": "grailed", "handle": "_snkr.haus", "standing": "active",
         "region": "US", "fee_pct": 0.12, "valid_from": "2026-01-01T00:00:00"},
        {"platform": "depop", "handle": "snkrhaus", "standing": "active",
         "region": "US", "fee_pct": 0.10, "valid_from": "2026-03-15T00:00:00"},
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

    # --- pinned eval fixtures (stable SKUs) --------------------------------
    # j4-military-s: listed, price change 21d ago, engagement, notes, as-of 14d
    j4_listed = NOW - timedelta(days=51)
    j4_reprice = NOW - timedelta(days=21)
    items.append(_item(
        sku="j4-military-s", product="Jordan 4 Retro — Military Black",
        variant="black/white", size="S", condition="like_new",
        acquisition_channel="retail", acquisition_cost_cny=4181,
        status="listed", target_price_usd=727.28,
        notes="synthetic: military black 4s",
    ))
    events += _events_for("j4-military-s", j4_listed - timedelta(days=19),
                          j4_listed - timedelta(days=13), j4_listed, None, 727.28)
    events.append({"item_sku": "j4-military-s", "event_type": "price_change",
                   "event_at": _iso(j4_reprice), "payload": {"price_usd": 699.0}})
    add_listing("j4-military-s", "grailed", 699.0, j4_listed, price_history=[
        (j4_listed, 727.28, "opened", "active"),
        (j4_reprice, 699.0, "price_change", "active"),
    ])
    engagement += _eng("j4-military-s", "grailed", j4_listed, 10, views_base=80,
                       watch_frac=0.12, offer_frac=0.02)
    notes.append({
        "note_id": "note-j4-military-wear", "kind": "seller_note",
        "object_type": "item", "object_id": "j4-military-s",
        "title": "Condition callout",
        "body": "Military Black 4s have light inner-sole wear. Call it used, not like-new.",
    })

    # stone-cargo-l: owned, never listed (insufficient reprice)
    items.append(_item(
        sku="stone-cargo-l", product="Stone Island — Cargo Pants",
        variant="green", size="L", category="catalog.bottoms", condition="new",
        acquisition_cost_cny=3943, status="owned", target_price_usd=628.85,
        notes="synthetic: unlisted capital",
    ))
    events += _events_for("stone-cargo-l", NOW - timedelta(days=40),
                          NOW - timedelta(days=34), None, None)
    notes.append({
        "note_id": "note-stone-cargo-photo", "kind": "seller_note",
        "object_type": "item", "object_id": "stone-cargo-l",
        "title": "Photography backlog",
        "body": "Still unlisted because studio time slipped. Hem has a faint oil mark.",
    })

    # j1-panda-m: sold with order
    panda_listed = NOW - timedelta(days=60)
    panda_sold = panda_listed + timedelta(days=8)
    items.append(_item(
        sku="j1-panda-m", product="Jordan 1 Low — Panda",
        variant="black/white", size="M", condition="used",
        acquisition_channel="retail", acquisition_cost_cny=2587,
        status="sold", target_price_usd=385.06,
        notes="synthetic: sold panda",
    ))
    events += _events_for("j1-panda-m", panda_listed - timedelta(days=12),
                          panda_listed - timedelta(days=6), panda_listed, panda_sold, 385.06)
    add_listing("j1-panda-m", "grailed", 385.06, panda_listed, status="sold",
                sold_at=panda_sold, sold_price=360.0)
    engagement += _eng("j1-panda-m", "grailed", panda_listed, 7, views_base=60,
                       watch_frac=0.1, offer_frac=0.04)
    orders.append({
        "order_id": "ord-j1-panda-m", "item_sku": "j1-panda-m", "platform": "grailed",
        "qty": 1, "price_usd": 360.0, "fees_usd": 43.2, "shipping_usd": 12.0,
        "status": "delivered", "order_at": _iso(panda_sold),
    })

    # carhartt-mich-m: listed with engagement (Q16/Q20)
    car_listed = NOW - timedelta(days=18)
    items.append(_item(
        sku="carhartt-mich-m", product="Carhartt WIP — Michigan Coat",
        variant="tobacco", size="M", category="catalog.outerwear",
        condition="like_new", acquisition_channel="private",
        acquisition_cost_cny=3307, status="listed", target_price_usd=610.5,
    ))
    events += _events_for("carhartt-mich-m", car_listed - timedelta(days=14),
                          car_listed - timedelta(days=8), car_listed, None, 610.5)
    add_listing("carhartt-mich-m", "grailed", 610.5, car_listed)
    engagement += _eng("carhartt-mich-m", "grailed", car_listed, 8, views_base=40,
                       watch_frac=0.15, offer_frac=0.01)

    # y350-onyx-s / fog-ess-hoodie-l: unlisted owned (attention)
    for sku, product, cat, cost, tgt, size in [
        ("y350-onyx-s", "Yeezy Boost 350 V2 — Onyx", "catalog.sneakers", 2305, 487.39, "S"),
        ("fog-ess-hoodie-l", "Fear of God Essentials — Hoodie", "catalog.tops", 1825, 263.85, "L"),
    ]:
        items.append(_item(sku=sku, product=product, size=size, category=cat,
                           acquisition_cost_cny=cost, status="owned",
                           target_price_usd=tgt, condition="new"))
        events += _events_for(sku, NOW - timedelta(days=28), NOW - timedelta(days=22), None, None)

    # --- required scenarios ------------------------------------------------
    # 1 sourced not received
    items.append(_item(sku="src-airmax-10", product="Nike Air Max 90 — Infrared",
                       size="10", status="in_transit", acquisition_cost_cny=2100,
                       target_price_usd=220.0, condition="new"))
    events += _events_for("src-airmax-10", NOW - timedelta(days=5), None, None, None)

    # 2 another in_transit
    items.append(_item(sku="src-aj5-11", product="Jordan 5 Retro — Fire Red",
                       size="11", status="in_transit", acquisition_cost_cny=2400,
                       target_price_usd=250.0))
    events += _events_for("src-aj5-11", NOW - timedelta(days=3), None, None, None)

    # 3 received never listed (extra)
    items.append(_item(sku="recv-nb2002-9", product="New Balance 2002R — Protection Pack",
                       size="9", status="owned", acquisition_cost_cny=1750,
                       target_price_usd=210.0, condition="new"))
    events += _events_for("recv-nb2002-9", NOW - timedelta(days=20),
                          NOW - timedelta(days=14), None, None)

    # 4 recently listed
    fresh_at = NOW - timedelta(days=2)
    items.append(_item(sku="fresh-samba-8", product="Adidas Samba OG — White/Gum",
                       size="8", status="listed", acquisition_cost_cny=980,
                       target_price_usd=165.0, condition="new"))
    events += _events_for("fresh-samba-8", NOW - timedelta(days=12),
                          NOW - timedelta(days=6), fresh_at, None, 165.0)
    add_listing("fresh-samba-8", "depop", 165.0, fresh_at)
    engagement += _eng("fresh-samba-8", "depop", fresh_at, 2, views_base=30,
                       watch_frac=0.1, offer_frac=0.0)

    # 5 stale listing
    stale_at = NOW - timedelta(days=28)
    items.append(_item(sku="stale-bogo-m", product="Supreme Box Logo Tee — Navy",
                       size="M", category="catalog.tops", status="listed",
                       acquisition_cost_cny=1600, target_price_usd=240.0, condition="like_new"))
    events += _events_for("stale-bogo-m", stale_at - timedelta(days=12),
                          stale_at - timedelta(days=6), stale_at, None, 240.0)
    add_listing("stale-bogo-m", "grailed", 240.0, stale_at)
    engagement += _eng("stale-bogo-m", "grailed", stale_at, 9, views_base=25,
                       watch_frac=0.06, offer_frac=0.0)

    # 6 high views / low watchers
    hv_at = NOW - timedelta(days=12)
    items.append(_item(sku="viewy-dunk-9", product="Nike Dunk Low — Panda",
                       size="9", status="listed", acquisition_cost_cny=1400,
                       target_price_usd=190.0))
    events += _events_for("viewy-dunk-9", hv_at - timedelta(days=10),
                          hv_at - timedelta(days=5), hv_at, None, 190.0)
    add_listing("viewy-dunk-9", "grailed", 190.0, hv_at)
    engagement += _eng("viewy-dunk-9", "grailed", hv_at, 8, views_base=200,
                       watch_frac=0.02, offer_frac=0.0)

    # 7 high watchers / zero offers  (Q11)
    hw_at = NOW - timedelta(days=11)
    items.append(_item(sku="watchy-aj3-10", product="Jordan 3 Retro — White Cement",
                       size="10", status="listed", acquisition_cost_cny=3200,
                       target_price_usd=280.0, condition="like_new"))
    events += _events_for("watchy-aj3-10", hw_at - timedelta(days=10),
                          hw_at - timedelta(days=5), hw_at, None, 280.0)
    add_listing("watchy-aj3-10", "grailed", 280.0, hw_at)
    engagement += _eng("watchy-aj3-10", "grailed", hw_at, 8, views_base=90,
                       watch_frac=0.22, offer_frac=0.0)

    # 8 multiple offers unsold
    of_at = NOW - timedelta(days=9)
    items.append(_item(sku="offers-yzy-7", product="Yeezy Slide — Onyx",
                       size="7", status="listed", acquisition_cost_cny=900,
                       target_price_usd=140.0, condition="new"))
    events += _events_for("offers-yzy-7", of_at - timedelta(days=8),
                          of_at - timedelta(days=4), of_at, None, 140.0)
    add_listing("offers-yzy-7", "depop", 140.0, of_at)
    engagement += _eng("offers-yzy-7", "depop", of_at, 7, views_base=70,
                       watch_frac=0.12, offer_frac=0.08)

    # 9 fast sale
    fs_list = NOW - timedelta(days=25)
    fs_sold = fs_list + timedelta(days=3)
    items.append(_item(sku="fast-j1-chicago-9", product="Jordan 1 High — Chicago Lost & Found",
                       size="9", status="sold", acquisition_cost_cny=4100,
                       target_price_usd=420.0, condition="used"))
    events += _events_for("fast-j1-chicago-9", fs_list - timedelta(days=10),
                          fs_list - timedelta(days=5), fs_list, fs_sold, 420.0)
    add_listing("fast-j1-chicago-9", "grailed", 420.0, fs_list, status="sold",
                sold_at=fs_sold, sold_price=410.0)
    engagement += _eng("fast-j1-chicago-9", "grailed", fs_list, 3, views_base=120,
                       watch_frac=0.18, offer_frac=0.06)
    orders.append({
        "order_id": "ord-fast-j1", "item_sku": "fast-j1-chicago-9", "platform": "grailed",
        "qty": 1, "price_usd": 410.0, "fees_usd": 49.2, "shipping_usd": 14.0,
        "status": "shipped", "order_at": _iso(fs_sold),
    })

    # 10 slow sale (depop — channel contrast)
    ss_list = NOW - timedelta(days=55)
    ss_sold = ss_list + timedelta(days=38)
    items.append(_item(sku="slow-asics-11", product="Asics Gel-Kayano 14 — Cream",
                       size="11", status="sold", acquisition_cost_cny=1500,
                       target_price_usd=175.0))
    events += _events_for("slow-asics-11", ss_list - timedelta(days=12),
                          ss_list - timedelta(days=6), ss_list, ss_sold, 175.0)
    add_listing("slow-asics-11", "depop", 175.0, ss_list, status="sold",
                sold_at=ss_sold, sold_price=155.0)
    engagement += _eng("slow-asics-11", "depop", ss_list, 9, views_base=20,
                       watch_frac=0.05, offer_frac=0.02)
    orders.append({
        "order_id": "ord-slow-asics", "item_sku": "slow-asics-11", "platform": "depop",
        "qty": 1, "price_usd": 155.0, "fees_usd": 15.5, "shipping_usd": 9.0,
        "status": "delivered", "order_at": _iso(ss_sold),
    })

    # 11 sale after repricing
    rp_list = NOW - timedelta(days=40)
    rp_cut = rp_list + timedelta(days=12)
    rp_sold = rp_cut + timedelta(days=6)
    items.append(_item(sku="reprice-sold-palace-m", product="Palace Tri-Ferg Hoodie — Black",
                       size="M", category="catalog.tops", status="sold",
                       acquisition_cost_cny=2200, target_price_usd=260.0))
    events += _events_for("reprice-sold-palace-m", rp_list - timedelta(days=10),
                          rp_list - timedelta(days=5), rp_list, rp_sold, 260.0)
    events.append({"item_sku": "reprice-sold-palace-m", "event_type": "price_change",
                   "event_at": _iso(rp_cut), "payload": {"price_usd": 230.0}})
    add_listing("reprice-sold-palace-m", "grailed", 230.0, rp_list, status="sold",
                sold_at=rp_sold, sold_price=230.0, price_history=[
                    (rp_list, 260.0, "opened", "active"),
                    (rp_cut, 230.0, "price_change", "active"),
                    (rp_sold, 230.0, "sold", "sold"),
                ])
    engagement += _eng("reprice-sold-palace-m", "grailed", rp_list, 8, views_base=50,
                       watch_frac=0.1, offer_frac=0.03)
    orders.append({
        "order_id": "ord-palace-reprice", "item_sku": "reprice-sold-palace-m",
        "platform": "grailed", "qty": 1, "price_usd": 230.0, "fees_usd": 27.6,
        "shipping_usd": 12.0, "status": "shipped", "order_at": _iso(rp_sold),
    })

    # 12 multiple price changes still listed
    ml_list = NOW - timedelta(days=24)
    ml_p1 = ml_list + timedelta(days=8)
    ml_p2 = ml_list + timedelta(days=16)
    items.append(_item(sku="reprice-live-kith-s", product="Kith Williams III Hoodie",
                       size="S", category="catalog.tops", status="listed",
                       acquisition_cost_cny=1900, target_price_usd=210.0))
    events += _events_for("reprice-live-kith-s", ml_list - timedelta(days=10),
                          ml_list - timedelta(days=5), ml_list, None, 210.0)
    add_listing("reprice-live-kith-s", "grailed", 185.0, ml_list, price_history=[
        (ml_list, 210.0, "opened", "active"),
        (ml_p1, 195.0, "price_change", "active"),
        (ml_p2, 185.0, "price_change", "active"),
    ])
    engagement += _eng("reprice-live-kith-s", "grailed", ml_list, 9, views_base=35,
                       watch_frac=0.09, offer_frac=0.01)

    # 13 multi-channel
    du_list = NOW - timedelta(days=16)
    items.append(_item(sku="dual-nb990-10", product="New Balance 990v6 — Grey",
                       size="10", status="listed", acquisition_cost_cny=2800,
                       target_price_usd=260.0, condition="new"))
    events += _events_for("dual-nb990-10", du_list - timedelta(days=12),
                          du_list - timedelta(days=6), du_list, None, 260.0)
    add_listing("dual-nb990-10", "grailed", 260.0, du_list)
    add_listing("dual-nb990-10", "depop", 245.0, du_list + timedelta(days=1))
    engagement += _eng("dual-nb990-10", "grailed", du_list, 7, views_base=45,
                       watch_frac=0.11, offer_frac=0.02)
    engagement += _eng("dual-nb990-10", "depop", du_list + timedelta(days=1), 6,
                       views_base=30, watch_frac=0.08, offer_frac=0.03)

    # 14 missing engagement
    me_list = NOW - timedelta(days=7)
    items.append(_item(sku="miss-eng-tee-l", product="Vintage Nike Mini Swoosh Tee",
                       size="L", category="catalog.tops", status="listed",
                       acquisition_cost_cny=1251, target_price_usd=229.53, condition="new"))
    events += _events_for("miss-eng-tee-l", me_list - timedelta(days=10),
                          me_list - timedelta(days=5), me_list, None, 229.53)
    add_listing("miss-eng-tee-l", "grailed", 229.53, me_list)

    # 15 missing acquisition cost
    items.append(_item(sku="miss-cost-hoodie-m", product="Unknown Blank Hoodie",
                       size="M", category="catalog.tops", status="owned",
                       acquisition_cost_cny=None, target_price_usd=90.0, condition="used"))
    events += _events_for("miss-cost-hoodie-m", NOW - timedelta(days=15),
                          NOW - timedelta(days=10), None, None)

    # 16 extra sold on grailed for channel stats
    g2_list = NOW - timedelta(days=48)
    g2_sold = g2_list + timedelta(days=11)
    items.append(_item(sku="sold-tn-9", product="Nike TN Air Max Plus — Black",
                       size="9", status="sold", acquisition_cost_cny=1700,
                       target_price_usd=200.0))
    events += _events_for("sold-tn-9", g2_list - timedelta(days=8),
                          g2_list - timedelta(days=4), g2_list, g2_sold, 200.0)
    add_listing("sold-tn-9", "grailed", 200.0, g2_list, status="sold",
                sold_at=g2_sold, sold_price=188.0)
    engagement += _eng("sold-tn-9", "grailed", g2_list, 8, views_base=55,
                       watch_frac=0.1, offer_frac=0.03)
    orders.append({
        "order_id": "ord-tn-9", "item_sku": "sold-tn-9", "platform": "grailed",
        "qty": 1, "price_usd": 188.0, "fees_usd": 22.56, "shipping_usd": 12.0,
        "status": "delivered", "order_at": _iso(g2_sold),
    })

    # filler owned / listed / sold to land in 60-100
    # Same lifecycle rules as named cohorts above (in-transit, unlisted,
    # listed, sold). Not independent random columns. Named SKUs are the
    # scenario fixtures; these rows add volume with coherent timestamps.
    filler = [
        ("fill-owned-01", "Nike Tech Fleece Joggers", "catalog.bottoms", "owned", 1100, 160),
        ("fill-owned-02", "Carhartt WIP Script Sweat", "catalog.tops", "owned", 900, 130),
        ("fill-owned-03", "Stone Island Compass Tee", "catalog.tops", "owned", 1500, 190),
        ("fill-owned-04", "NB 550 White/Green", "catalog.sneakers", "owned", 1300, 170),
        ("fill-owned-05", "Jordan 6 Metallic Silver", "catalog.sneakers", "owned", 3600, 310),
        ("fill-listed-01", "Dunk High Vintage Navy", "catalog.sneakers", "listed", 1250, 175),
        ("fill-listed-02", "Yeezy 700 Analog", "catalog.sneakers", "listed", 2700, 240),
        ("fill-listed-03", "Patagonia Better Sweater", "catalog.outerwear", "listed", 800, 120),
        ("fill-listed-04", "Arcteryx Atom LT", "catalog.outerwear", "listed", 2100, 250),
        ("fill-listed-05", "Clarks Wallabee Maple", "catalog.sneakers", "listed", 950, 140),
        ("fill-listed-06", "Salomon XT-6 White", "catalog.sneakers", "listed", 1600, 185),
        ("fill-sold-01", "Jordan 11 Concord", "catalog.sneakers", "sold", 3800, 340),
        ("fill-sold-02", "Nike Vomero 5", "catalog.sneakers", "sold", 1400, 165),
        ("fill-sold-03", "Stussy 8-Ball Tee", "catalog.tops", "sold", 700, 95),
        ("fill-sold-04", "Our Legacy Borrowed Shirt", "catalog.tops", "sold", 1800, 210),
        ("fill-transit-01", "Jordan 4 Thunder", "catalog.sneakers", "in_transit", 3000, 280),
        ("fill-transit-02", "Nike P-6000", "catalog.sneakers", "in_transit", 1100, 150),
        ("fill-owned-06", "Aime Leon Dore Track Pant", "catalog.bottoms", "owned", 2000, 230),
        ("fill-owned-07", "WWG Camo Cargo", "catalog.bottoms", "owned", 1600, 200),
        ("fill-listed-07", "Birkenstock Boston Taupe", "catalog.sneakers", "listed", 850, 125),
        ("fill-listed-08", "Crocs Classic Lined", "catalog.sneakers", "listed", 400, 70),
        ("fill-owned-08", "Uniqlo U Crewneck", "catalog.tops", "owned", 350, 55),
        ("fill-sold-05", "New Balance 1906R", "catalog.sneakers", "sold", 1550, 180),
        ("fill-owned-09", "Levi 501 '93", "catalog.bottoms", "owned", 600, 95),
        ("fill-listed-09", "Jordan 2 Python", "catalog.sneakers", "listed", 4200, 360),
        ("fill-owned-10", "Kapital Century Denim", "catalog.bottoms", "owned", 3100, 290),
        ("fill-sold-06", "Depop-channel sale filler", "catalog.tops", "sold", 500, 80),
        ("fill-owned-11", "Canvas Work Jacket", "catalog.outerwear", "owned", 180, 45),
        ("fill-owned-12", "Pique Polo Forest", "catalog.tops", "owned", 42, 28),
        ("fill-owned-13", "Pique Polo Sand", "catalog.tops", "owned", 42, 28),
        ("fill-owned-14", "Utility Cargo Short", "catalog.bottoms", "owned", 55, 32),
        ("fill-owned-16", "Ribbed Tank Black", "catalog.tops", "owned", None, 18),
        ("fill-listed-10", "Camp Collar Shirt", "catalog.tops", "listed", 48, 35),
        ("fill-listed-11", "Nylon Windbreaker", "catalog.outerwear", "listed", 95, 48),
        ("fill-listed-12", "Wide Chino Stone", "catalog.bottoms", "listed", 70, 40),
        ("fill-listed-13", "Terry Short Grey", "catalog.bottoms", "listed", 44, 30),
        ("fill-listed-14", "Logo Hoodie Navy", "catalog.tops", "listed", 88, 52),
        ("fill-listed-15", "Soccer Jersey Away", "catalog.tops", "listed", 60, 38),
        ("fill-sold-07", "Graphic Tee Wave", "catalog.tops", "sold", 35, 22),
        ("fill-sold-08", "Bucket Hat Olive", "catalog.accessories", "sold", 28, 20),
        ("fill-transit-03", "Quilted Liner", "catalog.outerwear", "in_transit", 75, 42),
        ("fill-planned-01", "Linen Overshirt", "catalog.outerwear", "planned", 65, 36),
        ("fill-owned-18", "Camp Cap Black", "catalog.accessories", "owned", None, 16),
        ("fill-listed-18", "Nylon Shoulder Bag", "catalog.accessories", "listed", 90, 48),
    ]
    for i, (sku, product, cat, status, cost, tgt) in enumerate(filler):
        size = ["S", "M", "L", "8", "9", "10"][i % 6]
        items.append(_item(sku=sku, product=product, size=size, category=cat,
                           acquisition_cost_cny=cost, status=status,
                           target_price_usd=float(tgt) if tgt else None,
                           condition=random.choice(["new", "like_new", "used"])))
        ordered = NOW - timedelta(days=15 + (i % 20))
        received = None if status == "in_transit" else ordered + timedelta(days=6)
        listed_at = None
        sold_at = None
        if status in ("listed", "sold"):
            listed_at = received + timedelta(days=4 + (i % 5)) if received else None
        if status == "sold" and listed_at:
            sold_at = listed_at + timedelta(days=5 + (i % 12))
        events += _events_for(sku, ordered, received, listed_at, sold_at, float(tgt))
        if listed_at:
            platform = "depop" if sku.endswith("06") or "Depop" in product else (
                "depop" if i % 4 == 0 else "grailed"
            )
            st = "sold" if status == "sold" else "active"
            add_listing(sku, platform, float(tgt), listed_at, status=st,
                        sold_at=sold_at, sold_price=(float(tgt) * 0.92 if sold_at else None))
            if i % 5 != 0:  # some missing engagement
                engagement += _eng(sku, platform, listed_at, min(8, 3 + i % 5),
                                   views_base=20 + i * 3, watch_frac=0.08,
                                   offer_frac=0.02 if status == "sold" else 0.01)
            if sold_at:
                orders.append({
                    "order_id": f"ord-{sku}", "item_sku": sku, "platform": platform,
                    "qty": 1, "price_usd": round(float(tgt) * 0.92, 2),
                    "fees_usd": round(float(tgt) * 0.1, 2), "shipping_usd": 11.0,
                    "status": "shipped", "order_at": _iso(sold_at),
                })

    notes.extend([
        {"note_id": "policy-grailed-fees", "kind": "policy", "object_type": "channel",
         "object_id": "grailed", "title": "Grailed seller fee (synthetic)",
         "body": "Synthetic policy excerpt: Grailed charges a seller fee on the sale price. Fee changes are versioned on the channel object."},
        {"note_id": "playbook-stale-listing", "kind": "playbook", "object_type": None,
         "object_id": None, "title": "Stale listing playbook",
         "body": "If an active listing is older than 14 days with no sale, review price and channel before cutting. High watch rate with zero offers is a price-friction signal."},
        {"note_id": "note-watchy-price", "kind": "seller_note", "object_type": "item",
         "object_id": "watchy-aj3-10", "title": "Watchers without offers",
         "body": "White Cement 3s are drawing saves but no offers. Ask is probably 20–30 over recent comps."},
    ])

    content = []
    snapshots = []
    tones = ["storyteller", "urgent", "informative", "minimal", "hype"]
    for i, sku in enumerate(["j4-military-s", "carhartt-mich-m", "fresh-samba-8",
                             "stale-bogo-m", "watchy-aj3-10", "dual-nb990-10",
                             "j1-panda-m", "fast-j1-chicago-9", "viewy-dunk-9"]):
        cid = f"cap-{sku}"
        tone = tones[i % len(tones)]
        content.append({
            "content_id": cid, "item_sku": sku, "body": f"Public listing copy for {sku}.",
            "tone": tone, "cta": "check pinned for sizing", "hooks": ["fit"],
            "status": "published", "published_at": _iso(NOW - timedelta(days=20 - i)),
            "platform": "grailed",
        })
        snapshots.append({
            "content_id": cid, "observed_at": _iso(NOW - timedelta(days=18 - i)),
            "window_hours": 48, "impressions": 200 + i * 15, "saves": 8 + i,
            "inquiries": 2 + (i % 3), "conversions": 1 if i % 3 == 0 else 0,
        })

    _w("channels.jsonl", channels)
    _w("catalog_items.jsonl", items)
    _w("item_events.jsonl", sorted(events, key=lambda e: e["event_at"] or ""))
    _w("listings.jsonl", listings)
    _w("listing_events.jsonl", listing_events)
    _w("engagement_metrics.jsonl", engagement)
    _w("orders.jsonl", orders)
    _w("notes.jsonl", notes)
    _w("content_pieces.jsonl", content)
    _w("content_snapshots.jsonl", snapshots)
    meta = {
        "name": "demo",
        "as_of": _iso(NOW),
        "seed": SEED,
        "purpose": "demo / development gold evaluation",
        "item_count": len(items),
        "calibration": (
            "Lifecycle mix is rounded from a real resale operation: mostly owned "
            "stock, a listed majority on the primary channel, sparse sold history, "
            "a few in-transit/planned rows, and occasional missing cost. Dual-channel "
            "and notes-on-items are scenario fixtures. Rows are fictional."
        ),
    }
    (OUT / "world.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"items={len(items)} listings={len(listings)} orders={len(orders)}")


if __name__ == "__main__":
    import argparse
    import subprocess
    import sys

    parser = argparse.ArgumentParser(description="Generate public synthetic worlds")
    parser.add_argument("--world", choices=["demo", "heldout", "all"], default="all")
    args = parser.parse_args()
    if args.world in {"demo", "all"}:
        generate()
    if args.world in {"heldout", "all"}:
        subprocess.run(
            [sys.executable, str(Path(__file__).with_name("generate_heldout_world.py"))],
            check=True,
        )
