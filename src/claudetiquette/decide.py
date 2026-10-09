"""Laya question and the rule that turns its answer into a yes or no.

The choice head is the gate. On convaiinnovations/laya 0.3.20, a noul
question about swearing scored ordinary requests in the same band as the
profane example, so the plugin does not use that score.
"""

from __future__ import annotations

REWRITE_LABELS = frozenset({"profane", "abusive"})

QUESTIONS = {
    "tone": {
        "type": "choice",
        "instructions": "How should `message` be labeled before it is sent to an assistant?",
        "criteria": {
            "clean": "No profanity and no insult. A normal, blunt, or annoyed request.",
            "profane": "Contains a swear word, even if the request itself is simple.",
            "abusive": "Insults, threatens, or is cruel toward the assistant or another person.",
        },
    }
}


def needs_rewrite(answer: dict | None) -> bool:
    """True when Laya's top label is profane or abusive."""
    if not answer:
        return False
    return answer.get("choice") in REWRITE_LABELS
