# FastAPI read layer

```bash
pip install -e ".[api]"
cdp serve
# http://127.0.0.1:8000/docs
```

View-backed routes read SQL. `/business/*`, `/context`, and `/ingest/trust` call the same Python tools as the CLI. Item routes retrieve a business object, not a table dump.

| Method | Path | Source |
|---|---|---|
| GET | `/health` | warehouse presence |
| GET | `/inventory/summary` | `catalog.v_inventory_summary` |
| GET | `/inventory/unlisted?limit=N` | `catalog.v_unlisted_queue` |
| GET | `/listings/performance?platform=X` | `sales.v_listing_performance` |
| GET | `/insights/voice-profiles` | current `insights.voice_profile` |
| GET | `/ingest/runs?limit=N` | `core.v_ingest_health` |
| GET | `/ingest/trust` | `observability.trust_report` |
| GET | `/context?question=&intent=&sku=` | `assemble_context` (question or intent required) |
| POST | `/answer` | `ground_answer` (plan + exact bundle + grounding) |
| GET | `/eval` | gold context-assembly eval |
| GET | `/eval/compare` | engine vs lexical baseline |
| GET | `/eval/answers` | FakeProvider grounded-answer contract |
| GET | `/business/snapshot` | `get_business_snapshot` |
| GET | `/business/attention?limit=N` | `get_inventory_attention_queue` |
| GET | `/business/metrics?name=` | metric registry / `explain_metric` |
| GET | `/business/items/{sku}` | `get_item` |
| GET | `/business/items/{sku}/history` | `get_item_history` |
| GET | `/business/channels/{platform}?as_of=&handle=` | `get_channel_as_of` |
| GET | `/business/actions` | sandbox action log |
| POST | `/business/actions` | propose sandbox action |
| POST | `/business/actions/{id}/approve` | human approve |
| POST | `/business/actions/{id}/reject` | human reject |

Auth, pooling, and multi-process serving are out of scope.
