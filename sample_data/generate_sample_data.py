#!/usr/bin/env python3
"""Compatibility wrapper — the public world lives in scripts/generate_public_world.py."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts" / "generate_public_world.py"), run_name="__main__")
