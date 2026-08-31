# Assumptions: synthetic data generation

Why the generated data looks the way it does. Each choice is a hypothesis;
the numbers are illustrative, not claims.

## Channel mix
- Split ~75/25 between Grailed and Depop. Grailed dominates resale
  sneakers and designer; Depop better for Y2K / lower-priced items.
- Platform fee difference (G 9% vs D 10%) baked in because it shows up
  downstream in margin math.

## Inventory status distribution
Roughly: 42% sold, 33% listed, 25% owned-not-listed.

Rationale: a working resale operation sells more than it sits on. The
unlisted pool (`owned`) creates the "go list these" question the
`v_unlisted_queue` view answers.

## Pricing
`target_price_usd = acquisition_cost_cny / 7.2 × uniform(1.15, 1.75)`
— CNY basis converted at CNY/USD ~7.2, margin band 15%–75% around a
baseline boutique multiplier. Real margins vary by category and rarity;
the band generates plausible heterogeneity.

## Listing lifecycle
Listings takes 10–25 days to go from "item received" to "listed" (time
for photography, grading, writing descriptions) and sell 2–14 days after
listing once priced reasonably.

## Engagement shaping
Views decay ~10%/day after listing (`0.9^day × jitter`) — recency
matters on marketplace pages, early views are a large fraction of total.

Watch rate 5–20% of views; offers are much rarer (0–5% of views).

## Content tones & conversion
Deliberately separated: `storyteller` content gets the highest
engagement-to-inquiry rate because detailed sizing/tooling/provenance
information reduces pre-sale anxiety on high-ticket resale. `hype` wins
raw impressions but converts worse — measurable in
`insights.v_content_effectiveness`.

## Content snapshot window
48 hours: long enough that algorithmic boosts have stabilized, short
enough to still be "about this drop."
