-- Analytics surface. Views are rebuilt on every `cdp init`/`cdp build`.

-- Latest projection health: everything sitting in inventory right now.
CREATE OR REPLACE VIEW catalog.v_inventory_summary AS
SELECT
  status,
  count(*)                                   AS items,
  sum(coalesce(qty_available, 0))            AS units_available,
  sum(coalesce(acquisition_cost_cny, 0)
      * coalesce(qty_available, 0))          AS invested_cny,
  round(sum(coalesce(acquisition_cost_cny, 0)
      * coalesce(qty_available, 0)) * 0.14, 2) AS invested_usd_est,
  sum(CASE WHEN status = 'listed' THEN 1 ELSE 0 END) AS listed_items
FROM catalog.items
GROUP BY status
ORDER BY 1;

-- Unlisted owned inventory, most capital first — the "go list these" queue.
CREATE OR REPLACE VIEW catalog.v_unlisted_queue AS
SELECT
  sku, product, variant, size, condition,
  acquisition_cost_cny,
  target_price_usd,
  updated_at
FROM catalog.items
WHERE status = 'owned'
ORDER BY coalesce(acquisition_cost_cny, 0) DESC;

-- Per-listing performance joining engagement snapshots with order outcomes.
CREATE OR REPLACE VIEW sales.v_listing_performance AS
SELECT
  l.listing_id,
  i.sku,
  i.product,
  ch.platform,
  l.price_usd,
  l.status                                        AS listing_status,
  l.listed_at,
  l.sold_at,
  l.sold_price_usd,
  coalesce(sum(e.views), 0)                       AS views,
  coalesce(sum(e.watchers), 0)                    AS watchers,
  coalesce(sum(e.offers), 0)                      AS offers,
  round(
    coalesce(sum(e.watchers), 0)::DOUBLE
      / nullif(coalesce(sum(e.views), 0), 0), 4)  AS watch_rate
FROM sales.listings l
JOIN catalog.items i      ON i.item_id = l.item_id
LEFT JOIN core.channels ch ON ch.channel_key = l.channel_key AND ch.valid_to IS NULL
LEFT JOIN sales.engagement_metric e ON e.listing_id = l.listing_id
GROUP BY l.listing_id, i.sku, i.product, ch.platform,
         l.price_usd, l.status, l.listed_at, l.sold_at, l.sold_price_usd;

-- Sell-through by channel cohort.
CREATE OR REPLACE VIEW sales.v_sell_through AS
SELECT
  ch.platform,
  count(*)                                            AS listings,
  sum(CASE WHEN l.status = 'sold' THEN 1 ELSE 0 END)  AS sold,
  round(sum(CASE WHEN l.status = 'sold' THEN 1 ELSE 0 END)::DOUBLE
        / nullif(count(*), 0), 3)                     AS sell_through_rate,
  round(avg(CASE WHEN l.sold_at IS NOT NULL
            THEN epoch(l.sold_at - l.listed_at) / 86400.0 END), 1) AS avg_days_to_sell,
  round(sum(l.sold_price_usd), 2)                     AS gross_sales_usd
FROM sales.listings l
LEFT JOIN core.channels ch ON ch.channel_key = l.channel_key AND ch.valid_to IS NULL
GROUP BY ch.platform
ORDER BY gross_sales_usd DESC NULLS LAST;

-- Content effectiveness: which tones/hooks produce conversion behavior.
CREATE OR REPLACE VIEW insights.v_content_effectiveness AS
SELECT
  c.tone,
  c.cta,
  count(*)                                AS pieces,
  sum(coalesce(s.impressions, 0))         AS impressions,
  sum(coalesce(s.saves, 0))               AS saves,
  sum(coalesce(s.inquiries, 0))           AS inquiries,
  sum(coalesce(s.conversions, 0))         AS conversions,
  round(avg(s.engagement_rate), 4)        AS avg_engagement_rate
FROM insights.content_pieces c
LEFT JOIN insights.content_snapshot s ON s.caption_id = c.caption_id
WHERE c.status = 'published'
GROUP BY c.tone, c.cta
ORDER BY avg_engagement_rate DESC NULLS LAST;

-- Ingest health: recent runs, rejections, freshness.
CREATE OR REPLACE VIEW core.v_ingest_health AS
SELECT
  source,
  status,
  started_at,
  duration_ms,
  rows_read,
  rows_loaded,
  rows_rejected,
  run_idempotency_key
FROM core.ingest_runs
ORDER BY started_at DESC;
