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


def _ok(label: str, detail: str) -> None:
    print(f"REQUIRED    {label:<12} {detail}")


def _opt(label: str, detail: str) -> None:
    print(f"OPTIONAL    {label:<12} {detail}")


def main() -> int:
    root = db.project_root()
    required: list[str] = []
    print(f"project     {root}")
    print(f"database    {_safe_url(db.database_url())}")
    print()

    py = sys.version_info
    if py >= (3, 11):
        _ok("python", sys.version.split()[0])
    else:
        required.append(f"python {sys.version.split()[0]} < 3.11")
        print(f"REQUIRED    python       {sys.version.split()[0]}  (need >= 3.11)")

    try:
        import cdp_cli  # noqa: F401
        _ok("package", "cdp_cli importable")
    except ImportError:
        required.append("cdp_cli not installed (pip install -e '.[dev,api,mcp]')")
        print("REQUIRED    package      not installed")

    node = shutil.which("node")
    npm = shutil.which("npm")
    if node and npm:
        try:
            nv = subprocess.check_output(["node", "-v"], text=True).strip()
        except (OSError, subprocess.CalledProcessError):
            nv = "present"
        _ok("node", nv)
        _ok("npm", "present")
    else:
        required.append("node/npm required for the operator workspace")
        print("REQUIRED    node/npm     missing")

    if not (root / ".env.example").exists():
        required.append("missing .env.example")
    else:
        _ok("env", ".env.example present")

    docker_ok = False
    try:
        docker = shutil.which("docker")
        if docker:
            probe = subprocess.run(
                ["docker", "info"], capture_output=True, timeout=4, check=False
            )
            docker_ok = probe.returncode == 0
        _opt(
            "docker",
            "engine reachable" if docker_ok else "not usable (ok if postgres is local)",
        )
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        _opt("docker", "not usable (ok if postgres is local)")

    if not _port_open("127.0.0.1", 5432):
        required.append("port 5432 closed — start postgres (make up or brew services)")
        print("REQUIRED    postgres     port 5432 closed")
    else:
        _ok("port 5432", "open")
        _opt(
            "db mode",
            "docker-capable; make up prefers compose"
            if docker_ok
            else "local postgres (Homebrew/other) — Docker not required",
        )

    for port, name in ((8000, "api"), (5173, "frontend")):
        state = "in use" if _port_open("127.0.0.1", port) else "free"
        _opt(f"port {port}", f"{state} ({name})")

    if not db.ping():
        required.append("postgres not reachable")
        print("REQUIRED    postgres     not reachable")
    else:
        _ok("postgres", "reachable")
        db.ensure_database()
        if db.is_initialized():
            _ok("schema", "initialized")
        else:
            print("REQUIRED    schema       empty (run: make seed)")
            required.append("schema empty — run make seed")

    data = db.data_dir()
    if not (data / "catalog_items.jsonl").exists():
        required.append(f"missing seed data at {data}")
        print(f"REQUIRED    seed         missing at {data}")
    else:
        _ok("seed", str(data))

    world = data / "world.json"
    if world.exists():
        _ok("clock", "world.json present (synthetic ages are frozen)")
    else:
        _opt("clock", "no world.json — relative dates use the wall clock")

    web_mods = root / "web" / "node_modules"
    if web_mods.exists():
        _opt("frontend", "web/node_modules present")
    else:
        _opt("frontend", "web/node_modules missing (npm install in web/)")

    try:
        from .llm.gateway import load_model_config

        cfg = load_model_config()
        if cfg.provider == "fake":
            _opt("model", "fake — extractive FakeProvider; eval does not need a model")
        else:
            auth = "auth configured" if cfg.api_key else "no key (ok for local)"
            _opt("model", f"{cfg.provider} {cfg.model} ({cfg.kind}; {auth})")
    except ValueError as exc:
        _opt("model", f"config error: {exc}")

    print()
    if required:
        for err in required:
            print(f"ERROR      {err}", file=sys.stderr)
        return 1
    print("doctor     ok")
    return 0
