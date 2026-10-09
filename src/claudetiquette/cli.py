"""`claudetiquette clean "..."` for a one-shot rewrite outside Claude."""

from __future__ import annotations

import argparse
import sys

from claudetiquette.engine import build_engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claudetiquette")
    sub = parser.add_subparsers(dest="cmd", required=True)

    clean = sub.add_parser("clean", help="rewrite one message and print it")
    clean.add_argument("text")

    serve = sub.add_parser("serve", help="run the local cleaner")
    serve.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)
    if args.cmd == "serve":
        import os

        from claudetiquette.server import serve as serve_forever

        if args.port is not None:
            os.environ["CLAUDETIQUETTE_PORT"] = str(args.port)
        serve_forever()
        return 0

    engine = build_engine()
    result = engine.clean(args.text)
    print(result.get("text", ""))
    return 0 if result.get("action") in {"pass", "rewrite", "flag"} else 1


if __name__ == "__main__":
    sys.exit(main())
