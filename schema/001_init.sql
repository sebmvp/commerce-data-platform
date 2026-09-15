-- Commerce Data Platform — canonical PostgreSQL schema
-- Operational truth for a small multi-channel resale operation.
-- JSONL under sample_data/ is the public synthetic seed, not a second truth.
--
-- Design notes:
--   * Natural keys support idempotent upserts.
--   * raw_json is kept on fact rows so a row can be re-interpreted.
--   * core.ingest_runs audits every batch (read/loaded/rejected).
--   * Channels are SCD-2: half-open [valid_from, valid_to)
--     (valid_to null = current). Point-in-time questions go through
--     get_channel_as_of.
--   * Items are event-sourced: catalog.item_events is append-only;
--     catalog.items is the latest projection.
--   * ops.actions is the sandbox propose/approve log (same database).
--   * ops.notes holds genuinely unstructured evidence (seller notes,
--     policies, playbooks) — not serialized tables.

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS supply;
CREATE SCHEMA IF NOT EXISTS sales;
CREATE SCHEMA IF NOT EXISTS ops;

-- ─────────────────────────────────────────────
-- CORE
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS core.channels (
  channel_key     TEXT PRIMARY KEY,
  platform        TEXT NOT NULL,
  handle          TEXT,
  standing        TEXT DEFAULT 'active',
  region          TEXT,
  fee_pct         DOUBLE PRECISION,
  valid_from      TIMESTAMP NOT NULL,
  valid_to        TIMESTAMP,
  source_file     TEXT,
  created_at      TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp),
  updated_at      TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE INDEX IF NOT EXISTS channels_platform_current
  ON core.channels (platform, handle)
  WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS core.taxonomy (
  category_key  TEXT PRIMARY KEY,
  label         TEXT NOT NULL,
  parent_key    TEXT,
  active        BOOLEAN DEFAULT true,
  source_file   TEXT,
  created_at    TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE TABLE IF NOT EXISTS core.ingest_runs (
  run_id          TEXT PRIMARY KEY,
  source          TEXT NOT NULL,
  run_key         TEXT,
  file_path       TEXT,
  file_hash       TEXT,
  started_at      TIMESTAMP NOT NULL,
  finished_at     TIMESTAMP,
  status          TEXT NOT NULL,
  rows_read       INTEGER DEFAULT 0,
  rows_loaded     INTEGER DEFAULT 0,
  rows_rejected   INTEGER DEFAULT 0,
  rejection_log   JSONB,
  error_message   TEXT,
  duration_ms     INTEGER,
  run_idempotency_key TEXT
);

CREATE INDEX IF NOT EXISTS ingest_runs_idem
  ON core.ingest_runs (run_idempotency_key, status);

CREATE TABLE IF NOT EXISTS core.rejected_records (
  rejected_id   TEXT PRIMARY KEY,
  run_id        TEXT NOT NULL REFERENCES core.ingest_runs (run_id),
  source        TEXT NOT NULL,
  record_key    TEXT,
  error_code    TEXT NOT NULL,
  detail        TEXT,
  raw_json      JSONB,
  created_at    TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE INDEX IF NOT EXISTS rejected_records_run
  ON core.rejected_records (run_id);

-- ─────────────────────────────────────────────
-- CATALOG
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS catalog.items (
  item_id         TEXT PRIMARY KEY,
  sku             TEXT UNIQUE NOT NULL,
  product         TEXT NOT NULL,
  variant         TEXT,
  size            TEXT,
  category_key    TEXT,
  condition       TEXT,
  acquisition_channel TEXT,
  acquisition_cost_cny DOUBLE PRECISION,
  qty             INTEGER DEFAULT 1,
  qty_available   INTEGER DEFAULT 1,
  status          TEXT DEFAULT 'planned',
  target_price_usd DOUBLE PRECISION,
  notes           TEXT,
  source_file     TEXT,
  raw_json        JSONB,
  created_at      TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp),
  updated_at      TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE TABLE IF NOT EXISTS catalog.item_events (
  event_id    TEXT PRIMARY KEY,
  item_id     TEXT NOT NULL REFERENCES catalog.items (item_id),
  event_type  TEXT NOT NULL,
  event_at    TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp),
  actor       TEXT,
  payload_json JSONB
);

CREATE INDEX IF NOT EXISTS item_events_item
  ON catalog.item_events (item_id, event_at);

-- ─────────────────────────────────────────────
-- SUPPLY
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS supply.purchase_orders (
  order_id          TEXT PRIMARY KEY,
  supplier          TEXT NOT NULL,
  currency          TEXT DEFAULT 'CNY',
  expected_delivery DATE,
  status            TEXT DEFAULT 'ordered',
  total_cny         DOUBLE PRECISION,
  shipping_cny      DOUBLE PRECISION,
  payload_json      JSONB,
  source_file       TEXT,
  created_at        TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp),
  updated_at        TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE TABLE IF NOT EXISTS supply.po_line_items (
  line_item_id  TEXT PRIMARY KEY,
  order_id      TEXT NOT NULL REFERENCES supply.purchase_orders (order_id),
  item_sku      TEXT,
  qty           INTEGER NOT NULL,
  unit_cny      DOUBLE PRECISION,
  payload_json  JSONB
);

-- ─────────────────────────────────────────────
-- SALES
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sales.listings (
  listing_id      TEXT PRIMARY KEY,
  item_id         TEXT NOT NULL REFERENCES catalog.items (item_id),
  channel_key     TEXT REFERENCES core.channels (channel_key),
  platform_url    TEXT,
  price_usd       DOUBLE PRECISION NOT NULL,
  status          TEXT DEFAULT 'active',
  listed_at       TIMESTAMP,
  sold_at         TIMESTAMP,
  sold_price_usd  DOUBLE PRECISION,
  source_file     TEXT,
  raw_json        JSONB,
  created_at      TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp),
  updated_at      TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE INDEX IF NOT EXISTS listings_item ON sales.listings (item_id);

-- Append-only listing timeline. Current sales.listings is the latest
-- projection. as-of questions walk these events.
CREATE TABLE IF NOT EXISTS sales.listing_events (
  event_id    TEXT PRIMARY KEY,
  listing_id  TEXT NOT NULL REFERENCES sales.listings (listing_id),
  event_type  TEXT NOT NULL,
  event_at    TIMESTAMP NOT NULL,
  price_usd   DOUBLE PRECISION,
  status      TEXT,
  payload_json JSONB
);

CREATE INDEX IF NOT EXISTS listing_events_listing
  ON sales.listing_events (listing_id, event_at);

CREATE TABLE IF NOT EXISTS sales.engagement_metric (
  metric_id   TEXT PRIMARY KEY,
  listing_id  TEXT NOT NULL REFERENCES sales.listings (listing_id),
  snapshot_at DATE NOT NULL,
  views       INTEGER DEFAULT 0,
  watchers    INTEGER DEFAULT 0,
  offers      INTEGER DEFAULT 0,
  raw_json    JSONB,
  UNIQUE (listing_id, snapshot_at)
);

CREATE TABLE IF NOT EXISTS sales.orders (
  order_line_key TEXT PRIMARY KEY,
  order_id      TEXT NOT NULL,
  line_no       INTEGER DEFAULT 1,
  channel_key   TEXT REFERENCES core.channels (channel_key),
  item_id       TEXT REFERENCES catalog.items (item_id),
  listing_id    TEXT REFERENCES sales.listings (listing_id),
  qty           INTEGER NOT NULL,
  price_usd     DOUBLE PRECISION NOT NULL,
  revenue_usd   DOUBLE PRECISION NOT NULL,
  fees_usd      DOUBLE PRECISION,
  shipping_usd  DOUBLE PRECISION,
  status        TEXT DEFAULT 'shipped',
  order_at      TIMESTAMP,
  payload_json  JSONB,
  source_file   TEXT,
  created_at    TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp),
  updated_at    TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE TABLE IF NOT EXISTS sales.order_events (
  event_id    TEXT PRIMARY KEY,
  order_id    TEXT NOT NULL,
  event_type  TEXT NOT NULL,
  event_at    TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp),
  payload_json JSONB
);

-- ─────────────────────────────────────────────
-- OPS: actions + unstructured evidence
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ops.actions (
  action_id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  action_type TEXT NOT NULL,
  proposed_payload JSONB NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL,
  decided_at TIMESTAMP,
  applied_at TIMESTAMP,
  actor TEXT NOT NULL,
  decided_by TEXT,
  recommendation_action TEXT,
  reason TEXT,
  decision_reason TEXT,
  supporting_context JSONB,
  context_question TEXT,
  previous_value JSONB,
  resulting_value JSONB
);

CREATE INDEX IF NOT EXISTS actions_status_created
  ON ops.actions (status, created_at DESC);

CREATE TABLE IF NOT EXISTS ops.notes (
  note_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  object_type TEXT,
  object_id TEXT,
  title TEXT,
  body TEXT NOT NULL,
  source_file TEXT,
  raw_json JSONB,
  created_at TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE INDEX IF NOT EXISTS notes_object
  ON ops.notes (object_type, object_id);

-- Lexical retrieval over unstructured evidence. Weighted title (A) > body (B),
-- GIN-indexed. query-level weighting lives in the search service.
ALTER TABLE ops.notes
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
  GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(body, '')), 'B')
  ) STORED;

CREATE INDEX IF NOT EXISTS notes_search_tsv
  ON ops.notes USING GIN (search_tsv);

-- Named checkpoints. Canonical history remains item_events / listing_events.
CREATE TABLE IF NOT EXISTS ops.business_snapshots (
  snapshot_id   TEXT PRIMARY KEY,
  captured_at   TIMESTAMP NOT NULL,
  as_of         TIMESTAMP NOT NULL,
  trigger       TEXT NOT NULL,
  payload_json  JSONB NOT NULL,
  content_hash  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS business_snapshots_captured
  ON ops.business_snapshots (captured_at DESC, as_of DESC);

-- Source lineage for canonical facts. effective_at is NULL when the
-- source did not provide a business timestamp — unknown, not invented.
CREATE TABLE IF NOT EXISTS core.record_lineage (
  lineage_id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  source_system TEXT NOT NULL,
  source_record_reference TEXT,
  content_hash TEXT,
  observed_at TIMESTAMP,
  effective_at TIMESTAMP,
  ingest_run_id TEXT REFERENCES core.ingest_runs (run_id),
  created_at TIMESTAMP DEFAULT (timezone('UTC', now())::timestamp)
);

CREATE INDEX IF NOT EXISTS record_lineage_entity
  ON core.record_lineage (entity_type, entity_id);
