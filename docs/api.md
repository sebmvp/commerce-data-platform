# FastAPI read layer

```bash
pip install -e ".[api]"
cdp serve
# http://127.0.0.1:8000/docs
```

View-backed routes read SQL. `/business/*` and `/ingest/trust` call the same Python tools as the CLI.

| Method | Path | Source |
|---|---|---|
| GET | `/health` | warehouse presence |
| GET | `/inventory/summary` | `catalog.v_inventory_summary` |
| GET | `/inventory/unlisted?limit=N` | `catalog.v_unlisted_queue` |
| GET | `/listings/performance?platform=X` | `sales.v_listing_performance` |
| GET | `/insights/voice-profiles` | current `insights.voice_profile` |
| GET | `/ingest/runs?limit=N` | `core.v_ingest_health` |
| GET | `/ingest/trust` | `observability.trust_report` |
| GET | `/business/snapshot` | `get_business_snapshot` |
| GET | `/business/attention?limit=N` | `get_inventory_attention_queue` |
| GET | `/business/metrics?name=` | metric registry / `explain_metric` |

Auth, pooling, and multi-process serving are out of scope.
