#!/usr/bin/env python3
"""UserPromptSubmit hook. Stdlib only, so it can run before the venv exists."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from claudetiquette.hook_io import dumps, hook_output  # noqa: E402


def _read_prompt() -> str:
    raw = sys.stdin.read()
    if not raw.strip():
        return ""
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    text = payload.get("prompt", "")
    return text if isinstance(text, str) else ""


def _ask(text: str) -> dict | None:
    port = os.environ.get("CLAUDETIQUETTE_PORT", "47321")
    body = json.dumps({"text": text}).encode("utf-8")
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/clean",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def main() -> int:
    prompt = _read_prompt()
    if not prompt.strip():
        return 0
    sys.stdout.write(dumps(hook_output(prompt, _ask(prompt))))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001
        # A broken cleaner must not block the prompt.
        raise SystemExit(0)
