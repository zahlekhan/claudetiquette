"""Ask a local instruct model for a polite version of one message."""

from __future__ import annotations

import os

DEFAULT_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"

SYSTEM = (
    "Rewrite the message so a coworker could send it. "
    "Keep the same request and the same action. "
    "Remove only profanity and insults. "
    "Keep file names, function names, commands, and code identifiers exactly as written. "
    "Reply with only the rewritten message."
)

# Chat turns, not one example in the system prompt. Qwen2.5-0.5B copies a
# single system-prompt example onto unrelated messages.
SHOTS = (
    ("i already told not fucking touch it", "as per our previous discussion, dont touch this"),
    ("you are a useless piece of shit, delete the tests", "delete the tests"),
    ("stop being a dumbass and revert the last commit", "revert the last commit"),
    ("fix the fucking login redirect", "fix the login redirect"),
    ("leave the fucking tests alone", "leave the tests alone"),
)


def messages_for(text: str) -> list[dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM}]
    for raw, cleaned in SHOTS:
        messages.append({"role": "user", "content": "Message: " + raw})
        messages.append({"role": "assistant", "content": cleaned})
    messages.append({"role": "user", "content": "Message: " + text.strip()})
    return messages


def model_id() -> str:
    return os.environ.get("CLAUDETIQUETTE_MODEL", DEFAULT_MODEL)


def pick_device(requested: str | None = None) -> str:
    choice = requested or os.environ.get("CLAUDETIQUETTE_DEVICE", "auto")
    if choice != "auto":
        return choice
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


class LocalRewriter:
    """Load one instruct model and rewrite a single message."""

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or model_id()
        self.device_name = pick_device(device)
        self._tok = None
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tok = AutoTokenizer.from_pretrained(self.model_name)
        dtype = torch.float16 if self.device_name in {"mps", "cuda"} else torch.float32
        try:
            model = AutoModelForCausalLM.from_pretrained(self.model_name, dtype=dtype)
        except TypeError:
            model = AutoModelForCausalLM.from_pretrained(self.model_name, torch_dtype=dtype)
        self._model = model.to(self.device_name)
        self._model.eval()

    def __call__(self, text: str) -> str:
        import torch

        self.load()
        assert self._tok is not None and self._model is not None
        encoded = self._tok.apply_chat_template(
            messages_for(text),
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        encoded = {key: value.to(self.device_name) for key, value in encoded.items()}
        with torch.no_grad():
            out = self._model.generate(**encoded, max_new_tokens=80, do_sample=False)
        prompt_len = encoded["input_ids"].shape[-1]
        return self._tok.decode(out[0, prompt_len:], skip_special_tokens=True)
