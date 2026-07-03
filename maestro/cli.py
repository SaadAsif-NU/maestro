"""Command-line entrypoint."""

from __future__ import annotations

import asyncio
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    import argparse

    from .env import load_env

    load_env()  # load a .env file if present

    parser = argparse.ArgumentParser(prog="maestro", description="Maestro multi-agent studio")
    parser.add_argument("--version", action="version", version=f"maestro {__version__}")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="Run the studio UI + API")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    run = sub.add_parser("run", help="Run a goal in the terminal and print the deliverable")
    run.add_argument("goal")
    run.add_argument("--researchers", type=int, default=2)

    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        uvicorn.run("maestro.server.app:app", host=args.host, port=args.port, reload=args.reload)
        return 0

    if args.command == "run":
        from .engine import Engine

        summary = asyncio.run(Engine().run_to_completion(args.goal, researchers=args.researchers))
        print(summary.deliverable)
        print(
            f"\n[{summary.agents} agents | {summary.total_tokens} tokens | "
            f"{summary.total_tool_calls} tool calls | {summary.elapsed_ms:.0f} ms]"
        )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
