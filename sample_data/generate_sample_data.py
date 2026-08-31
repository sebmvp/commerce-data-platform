#!/usr/bin/env python3
"""Generate the synthetic sample dataset.

Seeded and deterministic — the committed *.jsonl files are byte-for-byte
reproducible. See docs/assumptions.md for the reasoning behind each
distribution choice.

Usage: python sample_data/generate_sample_data.py
"""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(20260614)
OUT_DIR = Path(__file__).resolve().parent

CHANNELS = [
    {"platform": "grailed", "handle": "_snkr.haus", "standing": "active",
     "region": "US", "fee_pct": 0.09, "valid_from": "2025-01-01T00:00:00"},
    {"platform": "grailed", "handle": "_snkr.haus", "standing": "active",
     "region": "US", "fee_pct": 0.12, "valid_from": "2026-01-01T00:00:00"},
    {"platform": "depop", "handle": "snkrhaus", "standing": "active",
     "region": "US", "fee_pct": 0.10, "valid_from": "2026-03-15T00:00:00"},
]

PRODUCTS = [
    ("Jordan 4 Retro — Military Black", "j4-military", "sneakers", ["black/white"], 4200),
    ("Jordan 1 Low — Panda", "j1-panda", "sneakers", ["black/white"], 2200),
    ("Yeezy Boost 350 V2 — Onyx", "y350-onyx", "sneakers", ["onyx"], 2600),
    ("Supreme Box Logo Hoodie — Heather Grey", "bogo-hoodie-grey", "tops", ["grey"], 3200),
    ("Nike Tech Fleece — Cargo Shorts", "tech-cargo", "bottoms", ["olive"], 900),
    ("Carhartt WIP — Michigan Coat", "carhartt-mich", "outerwear", ["tobacco"], 2900),
    ("New Balance 992 — Grey", "nb-992-grey", "sneakers", ["grey"], 2400),
    ("Fear of God Essentials — Hoodie", "fog-ess-hoodie", "tops", ["taupe"], 1500),
    ("Adidas Samba OG — White/Brown", "samba-white", "sneakers", ["white/brown"], 1700),
    ("Vintage Nike Mini Swoosh Tee — 2004", "vtg-swoosh", "tops", ["black"], 1200),
    ("Stone Island — Cargo Pants", "stone-cargo", "bottoms", ["green"], 3800),
    ("Air Jordan 1 High — Hyper Royal", "j1-hyper", "sneakers", ["hyper white"], 5800),
]

TONES = ["urgent", "storyteller", "minimal", "hype", "informative"]
TONE_WEIGHTS = {"storyteller": 1.0, "urgent": 0.88, "informative": 0.84,
                "minimal": 0.79, "hype": 0.70}
CTAS = ["check pinned for sizing", "DM me 'fit' for details",
        "link in bio — first 3 get ship discount", "or lowest offer",
        "no trades — cash only"]

base = datetime(2026, 5, 1)


def _w(path: Path, filename: str, rows: list[dict]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with (path / filename).open("w") as f:
        for row in rows:
            f.write(json.dumps(row, default=str) + "\n")
    print(f"  {filename}: {len(rows)} rows")


def generate(out_dir: Path = OUT_DIR) -> None:
    items = []
    for i, (product, base_sku, cat, variants, cost_cny) in enumerate(PRODUCTS, 1):
        size_pool = ["8", "9", "10", "11", "M", "L"] if "sneakers" in base_sku else ["S", "M", "L"]
        size = random.choice(size_pool)
        status_roll = random.random()
        status = ("sold" if status_roll < 0.42 else
                  "listed" if status_roll < 0.75 else "owned")
        items.append({
            "sku": f"{base_sku}-{size.lower()}",
            "product": product,
            "variant": variants[0],
            "size": size,
            "category": f"catalog.{cat}" if cat in ("sneakers", "tops", "bottoms", "outerwear") else cat,
            "condition": random.choice(["new", "like_new", "used"]),
            "acquisition_channel": random.choice(["wholesale", "private", "retail"]),
            "acquisition_cost_cny": cost_cny + random.randint(-400, 600),
            "qty": 1,
            "status": status,
            "target_price_usd": round(cost_cny / 7.2 * random.uniform(1.15, 1.75), 2),
            "notes": random.choice([
                "from supplier manifest batch May 2026",
                "pulled from consignment rack",
                "bought off peak + priced to move",
                None,
            ]),
        })
    _w(out_dir, "channels.jsonl", CHANNELS)
    _w(out_dir, "catalog_items.jsonl", items)

    # item events: each item gets ordered -> received -> listed (maybe sold)
    events = []
    for item in items:
        t = base + timedelta(days=random.randint(0, 20))
        for etype, delta in [("ordered", 0), ("received", 6)]:
            events.append({"item_sku": item["sku"], "event_type": etype,
                           "event_at": (t + timedelta(days=delta)).isoformat(),
                           "actor": "batchimport",
                           "payload": {"supplier": "cnx433"} if etype == "ordered" else {}})
        listed_at: datetime | None = None
        if item["status"] in ("listed", "sold"):
            listed_at = t + timedelta(days=random.randint(10, 25))
            events.append({"item_sku": item["sku"], "event_type": "listed",
                           "event_at": listed_at.isoformat(),
                           "payload": {"price_usd": item["target_price_usd"]}})
        if item["status"] == "sold" and listed_at is not None:
            sold_at = listed_at + timedelta(days=random.randint(2, 14))
            events.append({"item_sku": item["sku"], "event_type": "sold",
                           "event_at": sold_at.isoformat()})
    events = sorted(events, key=lambda e: e["event_at"])
    _w(out_dir, "item_events.jsonl", events)

    listings = []
    for i, item in enumerate(items):
        if item["status"] not in ("listed", "sold"):
            continue
        platform = "grailed" if random.random() < 0.75 else "depop"
        price = item["target_price_usd"] * random.uniform(0.95, 1.08)
        listed_at = base + timedelta(days=random.randint(15, 45))
        sold = item["status"] == "sold"
        listings.append({
            "item_sku": item["sku"],
            "platform": platform,
            "platform_url": f"https://{platform}.com/listing/{uuid.uuid5(uuid.NAMESPACE_DNS, item['sku'])}"[:80],
            "price_usd": round(price, 2),
            "status": "sold" if sold else "active",
            "listed_at": listed_at.isoformat(),
            "sold_at": (listed_at + timedelta(days=random.randint(2, 20))).isoformat() if sold else None,
            "sold_price_usd": round(price * random.uniform(0.85, 1.0), 2) if sold else None,
        })
    _w(out_dir, "listings.jsonl", listings)

    engagement = []
    for listing in listings:
        sku = listing["item_sku"]
        platform = listing["platform"]
        start = datetime.fromisoformat(listing["listed_at"])
        days = (datetime.fromisoformat(listing["sold_at"]) - start).days if listing["sold_at"] else 12
        views_base = random.randint(40, 300)
        for d in range(1, min(days, 10) + 1):
            day_gain = int(views_base * (0.9 ** d) * random.uniform(0.6, 1.4))
            engagement.append({
                "listing_ref": sku,
                "platform": platform,
                "snapshot_at": (start + timedelta(days=d)).date().isoformat(),
                "views": max(3, day_gain),
                "watchers": max(0, int(day_gain * random.uniform(0.05, 0.20))),
                "offers": max(0, int(day_gain * random.uniform(0.0, 0.05))),
            })
    _w(out_dir, "engagement_metrics.jsonl", engagement)

    orders = []
    for i, listing in enumerate([l for l in listings if l["status"] == "sold"], 1):
        orders.append({
            "order_id": f"ORD-2026-{1000 + i}",
            "item_sku": listing["item_sku"],
            "platform": listing["platform"],
            "qty": 1,
            "price_usd": listing["sold_price_usd"],
            "fees_usd": round(listing["sold_price_usd"] * (0.09 if listing["platform"] == "grailed" else 0.10), 2),
            "shipping_usd": round(random.uniform(9, 18), 2),
            "status": "delivered",
            "order_at": listing["sold_at"],
        })
    _w(out_dir, "orders.jsonl", orders)

    pieces = []
    snippets = {
        "storyteller": "Found this in a sealed shipping box from the first May drop. Tagged, never tried on. Story is in the listing description.",
        "urgent": "Only 1 left in size {size} — these move fast. Price drops tonight.",
        "informative": "fit pics + measurements in listing. Picked for durability and comfort.",
        "minimal": "{product} — drops today.",
        "hype": "BANGER ALERT. This one is going to vanish. Don't sleep.",
    }

    for i, item in enumerate(items, 1):
        if item["status"] not in ("listed", "sold"):
            continue
        tone = random.choice(TONES)
        body = snippets[tone].format(size=item["size"] or "M", product=item["product"])
        published_at = base + timedelta(days=random.randint(10, 35))
        pieces.append({
            "content_id": f"pst-{100 + i}",
            "item_sku": item["sku"],
            "body": f"{body} {random.choice(CTAS)}",
            "tone": tone,
            "cta": random.choice(CTAS),
            "hooks": ["scarcity"] if tone in ("urgent", "hype") else [],
            "status": "published",
            "published_at": published_at.isoformat(),
            "platform": "grailed",
        })
    _w(out_dir, "content_pieces.jsonl", pieces)

    snapshots = []
    for piece in pieces:
        published = datetime.fromisoformat(piece["published_at"])
        instr = TONE_WEIGHTS.get(piece["tone"], 1.0) * random.uniform(100, 900)
        impressions = int(instr) + random.randint(-30, 100)
        saves = int(impressions * random.uniform(0.01, 0.07))
        inquiries = int(saves * random.uniform(0.05, 0.30))
        conversions = int(inquiries * random.uniform(0.0, 0.4))
        snapshots.append({
            "content_id": piece["content_id"],
            "observed_at": (published + timedelta(hours=48)).isoformat(),
            "window_hours": 48,
            "impressions": max(impressions, 5),
            "saves": saves,
            "inquiries": max(inquiries, 1),
            "conversions": conversions,
        })
    _w(out_dir, "content_snapshots.jsonl", snapshots)


if __name__ == "__main__":
    generate()
