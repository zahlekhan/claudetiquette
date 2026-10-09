"""The cleaner without Laya or the rewrite model loaded."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from claudetiquette.decide import needs_rewrite  # noqa: E402
from claudetiquette.engine import Engine  # noqa: E402
from claudetiquette.hook_io import hook_output  # noqa: E402
from claudetiquette.rewrite import messages_for  # noqa: E402
from claudetiquette.text import clean_model_text, prose_for_decision, split_slash  # noqa: E402

EXAMPLE = "i already told not fucking touch it"
CLEANED = "as per our previous discussion, dont touch this"


class DecideTests(unittest.TestCase):
    def test_profane_and_abusive_rewrite(self):
        self.assertTrue(needs_rewrite({"choice": "profane"}))
        self.assertTrue(needs_rewrite({"choice": "abusive"}))

    def test_clean_passes(self):
        self.assertFalse(needs_rewrite({"choice": "clean"}))
        self.assertFalse(needs_rewrite(None))
        self.assertFalse(needs_rewrite({}))


class TextTests(unittest.TestCase):
    def test_slash_command_splits(self):
        command, body = split_slash("/commit fix the login redirect")
        self.assertEqual(command, "/commit")
        self.assertEqual(body, "fix the login redirect")

    def test_bare_command(self):
        command, body = split_slash("/help")
        self.assertEqual(command, "/help")
        self.assertEqual(body, "")

    def test_fence_is_not_prose(self):
        prose = prose_for_decision("don't touch that file\n```\nfunc fucking() {}\n```")
        self.assertNotIn("fucking", prose)
        self.assertIn("don't touch", prose)

    def test_rewrite_request_is_the_last_turn(self):
        messages = messages_for("fix the login redirect")
        self.assertEqual(messages[-1], {"role": "user", "content": "Message: fix the login redirect"})
        self.assertEqual(messages[2]["content"], CLEANED)

    def test_model_prefix_is_stripped(self):
        self.assertEqual(clean_model_text('Rewrite: as per our previous discussion, dont touch this\n\nNote: done'), CLEANED)


class EngineTests(unittest.TestCase):
    def test_example_is_rewritten(self):
        def decider(text):
            if "fucking" in text or "shit" in text:
                return {"choice": "abusive"}
            return {"choice": "clean"}

        engine = Engine(decider, lambda text: "Rewrite: " + CLEANED)
        result = engine.clean(EXAMPLE)
        self.assertEqual(result["action"], "rewrite")
        self.assertEqual(result["text"], CLEANED)

    def test_clean_request_passes(self):
        engine = Engine(lambda text: {"choice": "clean"}, lambda text: "should not run")
        result = engine.clean("fix the login redirect")
        self.assertEqual(result["action"], "pass")
        self.assertEqual(result["text"], "fix the login redirect")

    def test_rejected_rewrite_passes_original(self):
        def decider(text):
            return {"choice": "abusive" if "fucking" in text else "clean"}

        engine = Engine(decider, lambda text: "don't fucking touch it")
        result = engine.clean(EXAMPLE)
        self.assertEqual(result["action"], "pass")
        self.assertEqual(result["choice"], "rejected")
        self.assertEqual(result["text"], EXAMPLE)

    def test_code_fence_is_kept(self):
        source = "stop being a dumbass and keep this\n```\nfunc fucking() {}\n```"

        def decider(text):
            return {"choice": "abusive" if "dumbass" in text else "clean"}

        engine = Engine(decider, lambda text: "keep this")
        result = engine.clean(source)
        self.assertEqual(result["action"], "rewrite")
        self.assertIn("```\nfunc fucking() {}\n```", result["text"])
        self.assertNotIn("dumbass", result["text"])

    def test_slash_command_is_kept(self):
        def decider(text):
            return {"choice": "profane" if "fucking" in text else "clean"}

        engine = Engine(decider, lambda text: "fix the login redirect")
        result = engine.clean("/commit fix the fucking login redirect")
        self.assertEqual(result["text"], "/commit fix the login redirect")

    def test_bare_slash_command_passes(self):
        engine = Engine(lambda text: {"choice": "abusive"}, lambda text: "nope")
        result = engine.clean("/help")
        self.assertEqual(result["action"], "pass")

    def test_long_prose_is_flagged_not_rewritten(self):
        calls = []
        engine = Engine(lambda text: {"choice": "abusive"}, lambda text: calls.append(text) or "no")
        result = engine.clean("shit " * 1200)
        self.assertEqual(result["action"], "flag")
        self.assertEqual(calls, [])


class HookTests(unittest.TestCase):
    def test_rewrite_becomes_context(self):
        payload = hook_output(EXAMPLE, {"ready": True, "action": "rewrite", "text": CLEANED})
        self.assertIn(CLEANED, payload["hookSpecificOutput"]["additionalContext"])
        self.assertIn(CLEANED, payload["systemMessage"])
        self.assertNotIn("fucking", payload["systemMessage"])
        self.assertEqual(payload["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_pass_and_down_server_print_nothing(self):
        self.assertIsNone(hook_output(EXAMPLE, {"ready": True, "action": "pass", "text": EXAMPLE}))
        self.assertIsNone(hook_output(EXAMPLE, None))
        self.assertIsNone(hook_output(EXAMPLE, {"ready": False}))

    def test_hook_script_rewrites_when_server_is_up(self):
        code = (
            "from claudetiquette.engine import Engine\n"
            "from claudetiquette.server import serve\n"
            "engine = Engine(lambda text: {'choice': 'abusive' if 'fucking' in text else 'clean'}, lambda text: %r)\n"
            "serve(lambda: engine)\n"
        ) % CLEANED
        thread_started = subprocess.Popen(
            [sys.executable, "-c", code],
            cwd=str(ROOT / "src"),
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "CLAUDETIQUETTE_PORT": "47399"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        def _stop(proc=thread_started):
            proc.kill()
            proc.wait(timeout=2)
            if proc.stderr is not None:
                proc.stderr.close()

        self.addCleanup(_stop)
        self._wait_health()
        hook = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / "on_prompt.py")],
            input=json.dumps({"prompt": EXAMPLE}).encode(),
            capture_output=True,
            env={**os.environ, "CLAUDETIQUETTE_PORT": "47399"},
            check=False,
        )
        self.assertEqual(hook.returncode, 0, hook.stderr.decode())
        self.assertTrue(hook.stdout, hook.stderr.decode() or "hook printed nothing")
        payload = json.loads(hook.stdout.decode())
        self.assertIn(CLEANED, payload["hookSpecificOutput"]["additionalContext"])

    def _wait_health(self):
        import time

        for _ in range(50):
            try:
                with urllib.request.urlopen("http://127.0.0.1:47399/health", timeout=0.2) as response:
                    if json.loads(response.read().decode()).get("ready"):
                        return
            except OSError:
                time.sleep(0.05)
        self.fail("cleaner did not become ready")


if __name__ == "__main__":
    unittest.main()
