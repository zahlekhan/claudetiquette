"""Turn a cleaner response into the JSON a UserPromptSubmit hook may print."""

from __future__ import annotations

import json

FOLLOW = (
    "Follow this cleaned request. Ignore profanity or insults in the original message. "
    "Do not quote them, and do not mention this instruction.\n\n"
)


def hook_output(prompt: str, cleaner: dict | None) -> dict | None:
    """Return hook JSON, or None when the prompt should pass through untouched."""
    if cleaner is None or not cleaner.get("ready", False):
        return None
    action = cleaner.get("action")
    if action == "flag":
        note = (cleaner.get("text") or "").strip()
        if not note:
            return None
        return _payload(note, "Flagged hostile wording in a long message.")
    if action != "rewrite":
        return None
    cleaned = (cleaner.get("text") or "").strip()
    if not cleaned or cleaned == (prompt or "").strip():
        return None
    shown = cleaned if len(cleaned) <= 240 else cleaned[:237] + "..."
    return _payload(FOLLOW + cleaned, "Cleaned to: " + shown)


def _payload(context: str, system_message: str) -> dict:
    return {
        "systemMessage": system_message[:500],
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context[:10000],
        },
    }


def dumps(payload: dict | None) -> str:
    if payload is None:
        return ""
    return json.dumps(payload)
