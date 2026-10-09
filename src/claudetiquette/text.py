"""Split a prompt into the part Laya should read and the part to keep."""

from __future__ import annotations

import re

FENCE = re.compile(r"```.*?```", re.DOTALL)
SLASH = re.compile(r"^(/[A-Za-z0-9_:-]+)(?:\s+|$)([\s\S]*)$")
REWRITE_PREFIX = re.compile(
    r"^(?:rewrite|rewritten|cleaned|message)\s*:\s*",
    re.IGNORECASE,
)

# A rewrite of a short message should stay short. The local model sometimes
# continues with a second example or a note.
MAX_REWRITE_CHARS = 2000


def split_slash(text: str) -> tuple[str | None, str]:
    """Return (command, body). A bare slash command has an empty body."""
    match = SLASH.match(text.strip())
    if not match:
        return None, text.strip()
    command, body = match.group(1), match.group(2).strip()
    return command, body


def prose_for_decision(text: str) -> str:
    """Drop fenced code so a swear inside a snippet does not flag the request."""
    return FENCE.sub(" ", text).strip()


def split_fences(text: str) -> list[str]:
    """Split text into prose and fenced blocks, keeping both."""
    return _split_keep_fences(text)


def _split_keep_fences(text: str) -> list[str]:
    parts: list[str] = []
    last = 0
    for match in FENCE.finditer(text):
        parts.append(text[last : match.start()])
        parts.append(match.group(0))
        last = match.end()
    parts.append(text[last:])
    return parts


def rewrite_prose(text: str, rewrite) -> str:
    """Rewrite prose and leave fenced code blocks unchanged."""
    chunks = []
    for part in _split_keep_fences(text):
        if part.startswith("```"):
            chunks.append(part)
        elif part.strip():
            chunks.append(rewrite(part))
        else:
            chunks.append(part)
    return "".join(chunks)


def clean_model_text(raw: str) -> str:
    """Keep the rewritten message and drop a label or a trailing note."""
    text = raw.strip().strip('"').strip()
    text = REWRITE_PREFIX.sub("", text).strip()
    # The model sometimes quotes the rewrite on the first line and explains after.
    first = text.split("\n", 1)[0].strip().strip('"')
    return first


def reattach(command: str | None, body: str) -> str:
    if command and body:
        return f"{command} {body}"
    if command:
        return command
    return body
