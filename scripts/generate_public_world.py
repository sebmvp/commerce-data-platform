#!/usr/bin/env python3
"""Thin wrapper. Generator lives in synthetic/resale (not runtime src/)."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "synthetic" / "resale" / "demo.py"), run_name="__main__")
