#!/usr/bin/env python3
"""SessionStart hook. Spawn the installer and return immediately.

Claude waits on this process. Model install and the first Laya load take
longer than a hook timeout, so the work runs in a detached process.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from claudetiquette.paths import data_dir  # noqa: E402


def _healthy(port: str) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return bool(payload.get("ready"))
    except (OSError, json.JSONDecodeError, TimeoutError):
        return False


def _plugin_version() -> str:
    try:
        meta = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    except (OSError, json.JSONDecodeError):
        return "0"
    return str(meta.get("version", "0"))


def _venv_python(data: Path) -> Path:
    if os.name == "nt":
        return data / "venv" / "Scripts" / "python.exe"
    return data / "venv" / "bin" / "python"


def _log(data: Path, message: str) -> None:
    with (data / "ensure.log").open("a", encoding="utf-8") as log:
        print(message, file=log, flush=True)


def install_and_serve() -> int:
    data = data_dir()
    port = os.environ.get("CLAUDETIQUETTE_PORT", "47321")
    if _healthy(port):
        _log(data, "already ready")
        return 0

    py = _venv_python(data)
    version_path = data / "installed-version"
    installed = version_path.read_text().strip() if version_path.exists() else ""
    current = _plugin_version()
    if not py.exists() or installed != current:
        _log(data, f"installing claudetiquette {current}")
        subprocess.check_call([sys.executable, "-m", "venv", str(data / "venv")])
        subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
        subprocess.check_call([str(py), "-m", "pip", "install", str(ROOT)])
        version_path.write_text(current + "\n")

    _log(data, "starting server")
    env = os.environ.copy()
    env["CLAUDETIQUETTE_PORT"] = port
    log_fd = os.open(data / "ensure.log", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o644)
    try:
        subprocess.Popen(
            [str(py), "-m", "claudetiquette.server"],
            cwd=str(ROOT),
            env=env,
            stdout=log_fd,
            stderr=log_fd,
            start_new_session=True,
        )
    finally:
        os.close(log_fd)
    return 0


def main() -> int:
    if "--worker" not in sys.argv:
        data = data_dir()
        log = (data / "ensure.log").open("a", encoding="utf-8")
        subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            stdout=log,
            stderr=log,
            start_new_session=True,
            env=os.environ.copy(),
        )
        return 0
    try:
        return install_and_serve()
    except Exception as exc:  # noqa: BLE001
        data = data_dir()
        with (data / "ensure.log").open("a", encoding="utf-8") as log:
            print(f"ensure failed: {exc}", file=log, flush=True)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
