#!/usr/bin/env python3
"""Start the visual Context Inspector (API + Vite) on a seeded database.

make demo  = this script
cdp demo   = CLI/system behavior story (isolated DB)
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "http://127.0.0.1:8000"
UI = "http://127.0.0.1:5173"
PYTHON = ROOT / ".venv" / "bin" / "python"
CDP = ROOT / ".venv" / "bin" / "cdp"


def _up(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as res:
            return 200 <= res.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _wait(url: str, label: str, seconds: float = 40) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _up(url):
            print(f"  {label} ready  {url}")
            return
        time.sleep(0.4)
    raise SystemExit(f"{label} did not start: {url}")


def main() -> int:
    env = os.environ.copy()
    env.setdefault("CDP_DATABASE_URL", "postgresql://cdp:cdp@127.0.0.1:5432/cdp")
    os.chdir(ROOT)

    subprocess.run(["make", "up"], check=False, cwd=ROOT)
    seed = subprocess.run([str(CDP), "build", "--sample"], cwd=ROOT, env=env)
    if seed.returncode != 0:
        print("seed failed; retrying with --force")
        subprocess.run([str(CDP), "build", "--sample", "--force"], check=True, cwd=ROOT, env=env)

    children: list[subprocess.Popen] = []

    def stop(*_: object) -> None:
        for proc in children:
            if proc.poll() is None:
                proc.send_signal(signal.SIGTERM)
        sys.exit(0)

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    if not _up(f"{API}/health"):
        children.append(
            subprocess.Popen(
                [str(CDP), "serve", "--host", "127.0.0.1", "--port", "8000"],
                cwd=ROOT,
                env=env,
            )
        )
        _wait(f"{API}/health", "API")
    else:
        print(f"  API already running  {API}")

    if not _up(UI):
        npm = subprocess.Popen(
            ["npm", "run", "dev", "--", "--port", "5173", "--host", "127.0.0.1"],
            cwd=ROOT / "web",
            env=env,
        )
        children.append(npm)
        _wait(UI, "frontend")
    else:
        print(f"  frontend already running  {UI}")

    print()
    print("Context Inspector   ", UI)
    print("API docs            ", f"{API}/docs")
    print()
    print("make demo  = visual product demo (this process)")
    print("cdp demo   = CLI/system behavior demo")
    print("Ctrl-C to stop.")
    while True:
        time.sleep(1)
        for proc in children:
            if proc.poll() is not None:
                return proc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
