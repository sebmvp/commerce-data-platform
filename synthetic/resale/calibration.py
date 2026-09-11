"""Classification of synthetic dimensions. Not all synthetic data is calibrated."""

CALIBRATED = "calibrated"
DOMAIN_REALISTIC = "domain_realistic"
ILLUSTRATIVE = "illustrative"

DIMENSIONS = {
    "operation_size": CALIBRATED,
    "state_mix": CALIBRATED,
    "acquisition_cost_missingness": CALIBRATED,
    "sourcing_channels": DOMAIN_REALISTIC,
    "product_category_mix": DOMAIN_REALISTIC,
    "owned_vs_listed": CALIBRATED,
    "dual_channel": ILLUSTRATIVE,
    "engagement_paths": ILLUSTRATIVE,
    "repricing_history": ILLUSTRATIVE,
    "notes_and_policies": ILLUSTRATIVE,
    "brand_and_variant_detail": DOMAIN_REALISTIC,
    "heldout_identifiers": ILLUSTRATIVE,
}


def classify(name: str) -> str:
    try:
        return DIMENSIONS[name]
    except KeyError as exc:
        known = ", ".join(sorted(DIMENSIONS))
        raise KeyError(f"unknown synthetic dimension {name!r}; known: {known}") from exc
