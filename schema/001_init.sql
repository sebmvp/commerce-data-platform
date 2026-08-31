-- Commerce Data Platform — schema v1
-- Analytical warehouse for a resale / marketplace commerce operation.
-- DuckDB dialect. Designed for reproducible rebuilds from canonical JSONL
-- inputs (see sample_data/), idempotent upserts, and auditable ingest runs.
--
-- Design notes:
--   * Every fact table carries a stable natural key used as the upsert key,
--     so re-running an ingest never duplicates rows.
--   * Raw source payloads (raw_json) are kept on fact rows so a row can be
--     re-interpreted without re-reading the original file.
--   * core.ingest_runs is an audit log: every ingest batch is recorded with
--     row counts, validation rejections, and duration.
--   * Channel snapshots are SCD-2 (valid_from/valid_to) so point-in-time
--     questions ("what did this account look like in June?") are answerable.
--   * Supply chain is event-sourced: items accumulate item_events; the item
--     row itself is the latest projection of its event stream.

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS supply;
CREATE SCHEMA IF NOT EXISTS sales;
CREATE SCHEMA IF NOT EXISTS insights;

-- ─────────────────────────────────────────────
-- CORE: shared dimensions + ingest audit
-- ─────────────────────────────────────────────

-- Selling channels (SCD-2): marketplace accounts change handles, standing,
-- and fee structures over time.
CREATE TABLE IF NOT EXISTS core.channels (
  channel_key     VARCHAR PRIMARY KEY,     -- deterministic hash of platform+handle
  platform        VARCHAR NOT NULL,        -- grailed | depop | ebay | ...
  handle          VARCHAR,
  standing        VARCHAR DEFAULT 'active',-- active | suspended | closed
  region          VARCHAR,
  fee_pct         DOUBLE,                  -- platform fee fraction at this version
  valid_from      TIMESTAMP NOT NULL,
  valid_to        TIMESTAMP,               -- null = current version
  source_file     VARCHAR,
  created_at      TIMESTAMP DEFAULT current_timestamp,
  updated_at      TIMESTAMP DEFAULT current_timestamp
);

-- Item taxonomy, self-referencing via parent_key (sneakers > jordan > jordan-1).
CREATE TABLE IF NOT EXISTS core.taxonomy (
  category_key  VARCHAR PRIMARY KEY,       -- slug path, e.g. 'sneakers/jordan'
  label         VARCHAR NOT NULL,
  parent_key    VARCHAR,                   -- FK logical to core.taxonomy
  active        BOOLEAN DEFAULT true,
  source_file   VARCHAR,
  created_at    TIMESTAMP DEFAULT current_timestamp
);

-- Audit log for every ingest batch. One row per (source, run).
CREATE TABLE IF NOT EXISTS core.ingest_runs (
  run_id          VARCHAR PRIMARY KEY,     -- uuid
  source          VARCHAR NOT NULL,        -- catalog.items | sales.orders | ...
  run_key         VARCHAR,                 -- deterministic batch key (idempotent re-runs)
  file_path       VARCHAR,
  file_hash       VARCHAR,                 -- sha256 of source file, for change detection
  started_at      TIMESTAMP NOT NULL,
  finished_at     TIMESTAMP,
  status          VARCHAR NOT NULL,        -- running | success | failed
  rows_read       INTEGER DEFAULT 0,
  rows_loaded     INTEGER DEFAULT 0,
  rows_rejected   INTEGER DEFAULT 0,
  rejection_log   JSON,                    -- [{row, reason, field}]
  error_message   VARCHAR,
  duration_ms     INTEGER,
  run_idempotency_key VARCHAR              -- sha256(source + file_hash)
);

-- One row per source row rejected by validation. Kept forever for audit.
CREATE TABLE IF NOT EXISTS core.rejected_records (
  rejected_id   VARCHAR PRIMARY KEY,
  run_id        VARCHAR NOT NULL,          -- FK logical to core.ingest_runs
  source        VARCHAR NOT NULL,
  record_key    VARCHAR,                   -- natural key if one was parseable
  error_code    VARCHAR NOT NULL,          -- schema_violation | missing_field | bad_type | duplicate
  detail        VARCHAR,
  raw_json      JSON,
  created_at    TIMESTAMP DEFAULT current_timestamp
);

-- ─────────────────────────────────────────────
-- CATALOG: what we hold, what it's worth, what happened to it
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS catalog.items (
  item_id         VARCHAR PRIMARY KEY,   -- uuid
  sku             VARCHAR UNIQUE NOT NULL,-- natural key: 'product — variant size'
  product         VARCHAR NOT NULL,
  variant         VARCHAR,
  size            VARCHAR,
  category_key    VARCHAR,               -- FK logical to core.taxonomy
  condition       VARCHAR,               -- new | like_new | used | worn
  acquisition_channel VARCHAR,           -- wholesale | private | retail
  acquisition_cost_cny DOUBLE,
  qty             INTEGER DEFAULT 1,
  qty_available   INTEGER DEFAULT 1,
  status          VARCHAR DEFAULT 'planned', -- planned | in_transit | owned | listed | sold | archived
  target_price_usd DOUBLE,
  notes           VARCHAR,
  source_file     VARCHAR,
  raw_json        JSON,
  created_at      TIMESTAMP DEFAULT current_timestamp,
  updated_at      TIMESTAMP DEFAULT current_timestamp
);

-- Event sourcing for the supply chain. An item's `status` is the latest
-- projection over this stream; rebuilding items from events is supported.
CREATE TABLE IF NOT EXISTS catalog.item_events (
  event_id    VARCHAR PRIMARY KEY,
  item_id     VARCHAR NOT NULL,          -- FK logical to catalog.items
  event_type  VARCHAR NOT NULL,          -- ordered | received | listed | price_change | sold | note
  event_at    TIMESTAMP DEFAULT current_timestamp,
  actor       VARCHAR,
  payload_json JSON
);

-- ─────────────────────────────────────────────
-- SUPPLY: inbound purchase orders from suppliers
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS supply.purchase_orders (
  order_id          VARCHAR PRIMARY KEY,   -- PO-<date>-<seq>
  supplier          VARCHAR NOT NULL,
  currency          VARCHAR DEFAULT 'CNY',
  expected_delivery DATE,
  status            VARCHAR DEFAULT 'ordered', -- draft | ordered | in_transit | delivered | partial
  total_cny         DOUBLE,
  shipping_cny      DOUBLE,
  payload_json      JSON,                  -- line items
  source_file       VARCHAR,
  created_at        TIMESTAMP DEFAULT current_timestamp,
  updated_at        TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS supply.po_line_items (
  line_item_id  VARCHAR PRIMARY KEY,
  order_id      VARCHAR NOT NULL,        -- FK logical to supply.purchase_orders
  item_sku      VARCHAR,
  qty           INTEGER NOT NULL,
  unit_cny      DOUBLE,
  payload_json  JSON
);

-- ─────────────────────────────────────────────
-- SALES: listings, engagement, orders
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sales.listings (
  listing_id      VARCHAR PRIMARY KEY,   -- uuid
  item_id         VARCHAR NOT NULL,      -- FK logical to catalog.items
  channel_key     VARCHAR,               -- FK logical to core.channels
  platform_url    VARCHAR,
  price_usd       DOUBLE NOT NULL,
  status          VARCHAR DEFAULT 'active', -- draft | active | sold | ended
  listed_at       TIMESTAMP,
  sold_at         TIMESTAMP,
  sold_price_usd  DOUBLE,
  source_file     VARCHAR,
  raw_json        JSON,
  created_at      TIMESTAMP DEFAULT current_timestamp,
  updated_at      TIMESTAMP DEFAULT current_timestamp
);

-- Daily engagement snapshots per listing.
CREATE TABLE IF NOT EXISTS sales.engagement_metric (
  metric_id   VARCHAR PRIMARY KEY,
  listing_id  VARCHAR NOT NULL,          -- FK logical to sales.listings
  snapshot_at DATE NOT NULL,
  views       INTEGER DEFAULT 0,
  watchers    INTEGER DEFAULT 0,
  offers      INTEGER DEFAULT 0,
  raw_json    JSON,
  UNIQUE (listing_id, snapshot_at)       -- one snapshot per listing per day
);

CREATE TABLE IF NOT EXISTS sales.orders (
  order_line_key VARCHAR PRIMARY KEY,    -- order_id + ':' + line_no
  order_id      VARCHAR NOT NULL,
  line_no       INTEGER DEFAULT 1,
  channel_key   VARCHAR,
  item_id       VARCHAR,
  listing_id    VARCHAR,
  qty           INTEGER NOT NULL,
  price_usd     DOUBLE NOT NULL,
  revenue_usd   DOUBLE NOT NULL,
  fees_usd      DOUBLE,
  shipping_usd  DOUBLE,
  status        VARCHAR DEFAULT 'shipped', -- shipped | delivered | returned | cancelled
  order_at      TIMESTAMP,
  payload_json  JSON,
  source_file   VARCHAR,
  created_at    TIMESTAMP DEFAULT current_timestamp,
  updated_at    TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS sales.order_events (
  event_id    VARCHAR PRIMARY KEY,
  order_id    VARCHAR NOT NULL,
  event_type  VARCHAR NOT NULL,          -- shipped | delivered | returned | cancelled
  event_at    TIMESTAMP DEFAULT current_timestamp,
  payload_json JSON
);

-- ─────────────────────────────────────────────
-- INSIGHTS: behavior + content performance layer
-- ─────────────────────────────────────────────
-- Content published about listings, and the engagement it drew, feeding a
-- distilled "voice profile": which tones *actually convert* to watching /
-- buying behavior. The profile is the primary fact a copywriter (human or
-- model) should write from next.

CREATE TABLE IF NOT EXISTS insights.content_pieces (
  caption_id  VARCHAR PRIMARY KEY,
  item_sku    VARCHAR,
  channel_key VARCHAR,
  body        VARCHAR NOT NULL,
  tone        VARCHAR,                   -- urgent | storyteller | minimal | hype | informative
  cta         VARCHAR,                   -- call-to-action style
  hooks       VARCHAR[],                 -- detected rhetorical hooks
  status      VARCHAR DEFAULT 'draft',   -- draft | published | retired
  published_at TIMESTAMP,
  engagement_rate DOUBLE,                -- aggregate, refreshed by insights.aggregate
  raw_json    JSON,
  created_at  TIMESTAMP DEFAULT current_timestamp,
  updated_at  TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS insights.engagement_events (
  event_id      VARCHAR PRIMARY KEY,
  caption_id    VARCHAR NOT NULL,        -- FK logical to insights.content_pieces
  event_type    VARCHAR NOT NULL,        -- view | comment | save | share | inquiry | listing_click
  occurred_at   TIMESTAMP NOT NULL,
  viewer_key    VARCHAR,                 -- opaque pseudonymous viewer id (never PII)
  channel_key   VARCHAR,
  payload_json  JSON
);

-- Rolling engagement snapshots per content piece (like post_metrics).
CREATE TABLE IF NOT EXISTS insights.content_snapshot (
  snapshot_id     VARCHAR PRIMARY KEY,
  caption_id      VARCHAR NOT NULL,
  observed_at     TIMESTAMP NOT NULL,
  window_hours    INTEGER,               -- 24 | 48 | 168
  impressions     BIGINT,
  interactions    BIGINT,
  saves           BIGINT,
  inquiries       BIGINT,
  engagement_rate DOUBLE,
  conversions     INTEGER,               -- inquiries that led to listings
  source          VARCHAR DEFAULT 'derived',
  raw_json        JSON
);

-- The distilled "voice profile" — aggregated from content_snapshot +
-- engagement_events by (tone, hook). One current version per (tone, hook).
CREATE TABLE IF NOT EXISTS insights.voice_profile (
  profile_id      VARCHAR PRIMARY KEY,
  content_type    VARCHAR NOT NULL,      -- listing_description | listing_drop | restock
  tone            VARCHAR NOT NULL,
  hook_style      VARCHAR,               -- size_scarcity | provenance | price_anchor | none
  channel_key     VARCHAR,
  sample_size     INTEGER NOT NULL,
  avg_watchers    DOUBLE,                -- avg new watchers per published content
  avg_conversion  DOUBLE,                -- avg listings sold per published content
  summary_md      VARCHAR,
  rules_json      JSON,
  version         INTEGER NOT NULL DEFAULT 1,
  is_current      BOOLEAN DEFAULT true,
  source_window_start TIMESTAMP,
  source_window_end   TIMESTAMP,
  created_at      TIMESTAMP DEFAULT current_timestamp,
  PRIMARY KEY (content_type, tone, hook_style, channel_key, version)
);

-- Conversion funnels: aggregate daily or weekly per channel.
CREATE TABLE IF NOT EXISTS insights.conversion_funnels (
  funnel_id      VARCHAR PRIMARY KEY,
  period         VARCHAR NOT NULL,       -- 'daily' | 'weekly'
  channel_key    VARCHAR,
  cohort         VARCHAR,                -- 'all_buyers' | item_category | ...
  impressions    BIGINT,
  inquiries      BIGINT,
  conversions    INTEGER,                -- listings sold
  funnel_start   DATE NOT NULL,
  funnel_end     DATE NOT NULL,
  updated_at     TIMESTAMP DEFAULT current_timestamp,
  UNIQUE (period, channel_key, cohort, funnel_start)
);
