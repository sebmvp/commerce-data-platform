"""Formatting of business payloads — no warehouse required."""
from cdp_cli.present import format_attention, format_snapshot, format_trust


def test_format_snapshot_uses_real_metric_fields():
    text = format_snapshot(
        {
            "capital_items": 6,
            "owned_unlisted": 3,
            "active_listings": 3,
            "stale_active_listings": 3,
            "stale_listing_days_threshold": 14,
            "orders": 6,
            "capital_tied_up_cny": 16812.0,
            "realized_revenue_usd": 3153.83,
            "realized_gross_after_fees_usd": 2793.2,
            "warehouse_trust_ok": True,
            "warehouse_trust_reasons": [],
        }
    )
    assert "BUSINESS STATE" in text
    assert "Owned inventory" in text
    assert "16,812 CNY" in text
    assert "not full margin" in text
    assert "OK" in text


def test_format_attention_labels_actions():
    text = format_attention(
        {
            "recommendations": [
                {
                    "sku": "stone-cargo-l",
                    "action": "list_next",
                    "based_on": {
                        "attention_reason": "unlisted_owned",
                        "acquisition_cost_cny": 3943.0,
                        "inventory_age_days": 106,
                        "listing_age_days": None,
                        "watch_rate": None,
                    },
                }
            ]
        }
    )
    assert "LIST NEXT" in text
    assert "stone-cargo-l" in text
    assert "3,943 CNY" in text
    assert "held 106 days" in text


def test_format_trust_ok():
    text = format_trust(
        {
            "ok": True,
            "reasons": [],
            "total_rejected_records": 2,
            "failed_runs": 0,
            "orphaned_running": 0,
            "unbalanced_success_runs": 0,
        }
    )
    assert "WAREHOUSE TRUST" in text
    assert "Rejected records" in text
    assert "2" in text
