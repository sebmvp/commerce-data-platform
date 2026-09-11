"""Synthetic resale world generation. Not imported by the runtime platform."""

from .calibration import CALIBRATED, DIMENSIONS, DOMAIN_REALISTIC, ILLUSTRATIVE
from .validate import validate_world

__all__ = [
    "CALIBRATED",
    "DIMENSIONS",
    "DOMAIN_REALISTIC",
    "ILLUSTRATIVE",
    "validate_world",
]
