"""Where the plugin and its private data live."""

from __future__ import annotations

import os
from pathlib import Path


def plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    # src/claudetiquette/paths.py -> plugin root
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_DATA") or os.environ.get("CLAUDETIQUETTE_DATA")
    path = Path(env) if env else Path.home() / ".local" / "share" / "claudetiquette"
    path.mkdir(parents=True, exist_ok=True)
    return path


def version_file() -> Path:
    return plugin_root() / ".claude-plugin" / "plugin.json"
