"""Local environment checks for `make doctor`."""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys

from urllib.parse import urlparse, urlunparse

from . import db


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.password:
        host = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        user = parsed.username or ""
        netloc = f"{user}:***@{host}{port}"
        return urlunparse(parsed._replace(netloc=netloc))
    return url


def _port_open(host: str, port: int) -> bool:
    sock = socket.socket()
    sock.settimeout(0.4)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def main() -> int:
    root = db.project_root()
    errors: list[str] = []
    print(f"python     {sys.version.split()[0]}")
    print(f"project    {root}")
    print(f"database   {_safe_url(db.database_url())}")

    if not (root / ".env.example").exists():
        errors.append("missing .env.example")
    else:
        print("env        .env.example present")

    docker_ok = False
    try:
        docker = shutil.which("docker")
        if docker:
            probe = subprocess.run(
                ["docker", "info"], capture_output=True, timeout=4
            )
            docker_ok = probe.returncode == 0
        print(
            "docker     "
            + ("engine reachable" if docker_ok else "not usable (optional if postgres is local)")
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        print("docker     not usable (optional if postgres is local)")

    if not _port_open("127.0.0.1", 5432):
        errors.append("port 5432 closed — start postgres (make up or brew services)")
    else:
        mode = "docker compose or local listener"
        print(f"port 5432  open ({mode})")
        print(
            "db mode    "
            + ("docker-capable; make up prefers compose" if docker_ok else "local postgres (Homebrew/other) — Docker not required")
        )

    for port, name in ((8000, "api"), (5173, "frontend")):
        state = "in use" if _port_open("127.0.0.1", port) else "free"
        print(f"port {port}  {state} ({name})")

    if not db.ping():
        errors.append("postgres not reachable")
    else:
        print("postgres   reachable")
        db.ensure_database()
        if db.is_initialized():
            print("schema     initialized")
        else:
            print("schema     empty (run: make seed)")

    data = db.data_dir()
    if not (data / "catalog_items.jsonl").exists():
        errors.append(f"missing seed data at {data}")
    else:
        print(f"seed       {data}")

    if errors:
        for err in errors:
            print(f"ERROR      {err}", file=sys.stderr)
        return 1
    print("doctor     ok")
    return 0
