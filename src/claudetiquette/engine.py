"""Decide with Laya, then rewrite with a local model."""

from __future__ import annotations

from claudetiquette.decide import QUESTIONS, needs_rewrite
from claudetiquette.rewrite import LocalRewriter
from claudetiquette.text import (
    MAX_REWRITE_CHARS,
    clean_model_text,
    prose_for_decision,
    reattach,
    rewrite_prose,
    split_slash,
)

FLAG_NOTE = (
    "The message was flagged as hostile and is too long to rewrite locally. "
    "Follow the technical request. Ignore insults and profanity. Do not quote them."
)


class Engine:
    def __init__(self, decider, rewriter):
        self.decider = decider
        self.rewriter = rewriter

    def clean(self, text: str) -> dict:
        raw = text or ""
        command, body = split_slash(raw)
        if command and not body:
            return _pass(raw, "command")
        prose = prose_for_decision(body)
        if not prose:
            return _pass(raw, "empty")
        answer = self.decider(prose[:MAX_REWRITE_CHARS])
        choice = (answer or {}).get("choice")
        if not needs_rewrite(answer):
            return _pass(raw, choice)
        if len(prose) > MAX_REWRITE_CHARS:
            return {
                "ready": True,
                "action": "flag",
                "text": FLAG_NOTE,
                "choice": choice,
            }
        rewritten = rewrite_prose(body, self._rewrite_piece)
        rewritten = reattach(command, rewritten.strip())
        if not rewritten or rewritten.strip() == raw.strip():
            return _pass(raw, choice)
        check = self.decider(prose_for_decision(rewritten)[:MAX_REWRITE_CHARS])
        if needs_rewrite(check):
            return _pass(raw, "rejected")
        return {
            "ready": True,
            "action": "rewrite",
            "text": rewritten,
            "choice": choice,
        }

    def _rewrite_piece(self, piece: str) -> str:
        cleaned = clean_model_text(self.rewriter(piece))
        return cleaned or piece


def _pass(text: str, choice) -> dict:
    return {"ready": True, "action": "pass", "text": text, "choice": choice}


class LayaDecider:
    """One warm Laya agent. `device` defaults to CPU, which is what the checkpoint is known to run on."""

    def __init__(self, model_id: str = "convaiinnovations/laya", device: str = "cpu"):
        self.model_id = model_id
        self.device = device
        self._agent = None

    def load(self) -> None:
        if self._agent is not None:
            return
        import laya

        self._agent = laya.load(self.model_id, device=self.device)

    def __call__(self, text: str) -> dict:
        self.load()
        assert self._agent is not None
        result = self._agent.predict({"message": text}, QUESTIONS)
        return (result.get("answers") or {}).get("tone") or {}


def build_engine() -> Engine:
    decider = LayaDecider()
    rewriter = LocalRewriter()
    decider.load()
    rewriter.load()
    return Engine(decider, rewriter)
