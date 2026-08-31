# FastAPI read layer

Ships in the `[api]` extra. Run:

```bash
pip install -e ".[api]"
cdp serve
# docs at http://127.0.0.1:8000/docs
```

The API is deliberately thin: it reads the warehouse views, it doesn't
own business logic. SQL is still the source of truth.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | 503 if warehouse missing, else db path |
| GET | `/inventory/summary` | `catalog.v_inventory_summary` |
| GET | `/inventory/unlisted?limit=N` | `catalog.v_unlisted_queue` top N |
| GET | `/listings/performance?platform=X` | `sales.v_listing_performance` (filterable) |
| GET | `/insights/voice-profiles` | current `insights.voice_profile` rows |
| GET | `/ingest/runs?limit=N` | recent `core.v_ingest_health` |

## Adding an endpoint

1. Express the question as a SQL view under `sql/views.sql` (if it
   doesn't exist already).
2. Add a route that just executes the view and maps to dicts.

If the answer requires new business logic, that logic belongs in the
ingest pipeline or the views — not in the API.

## Production notes (not done here)
- Auth / rate limiting: outside scope for a read-only analytics surface.
- Connection pooling / async: DuckDB connections are cheap; the current
  pattern (open per request, close) works at single-process scale.
