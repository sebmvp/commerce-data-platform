"""Guard against GitHub log-redaction leaking into executable URLs."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
URL = re.compile(r"postgres(?:ql)?://[^\s\"'`]+")

# Files that are executed or copied into a process environment.
# doctor.py may mask passwords as "***" for display — that is allowed.
EXECUTABLE = (
    ".github/workflows/test.yml",
    "Makefile",
    "docker-compose.yml",
    ".env.example",
    ".vscode/launch.json",
    "src/cdp_cli/db.py",
    "scripts/run_visual_demo.py",
)


def test_executable_database_urls_are_not_log_redactions() -> None:
    for rel in EXECUTABLE:
        text = (ROOT / rel).read_text()
        urls = URL.findall(text)
        assert urls, f"{rel} should contain a postgres URL"
        for raw in urls:
            url = raw.rstrip(")`.,")
            password = urlparse(url).password
            assert password != "***", (
                f"{rel} has a GitHub-redacted password in {url!r}. "
                "The disposable local/CI password is 'cdp'."
            )
            assert password, f"{rel} is missing a password in {url!r}"
