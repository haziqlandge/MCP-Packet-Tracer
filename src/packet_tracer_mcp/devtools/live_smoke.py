"""Run MCP tool calls from THIS checkout against a live Packet Tracer.

The client's running `packet-tracer` server keeps whatever code it started
with; this harness registers the tools of the current tree instead, so a live
check always exercises the code on disk.

Run from the repo root:
    python -m src.packet_tracer_mcp.devtools.live_smoke tests/live/headless.json
then filter the output:
    | grep -E "^=====|Traceback|NameError|PT_ERROR"

Each list entry is {"tool": name, ...args}. One failure never stops the run.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ..adapters.mcp.bridge_context import BridgeContext
from ..adapters.mcp.tool_registry import register_tools


def _text(result: object) -> str:
    # FastMCP.call_tool returns content blocks, or (blocks, structured) when the
    # tool has an output schema; only the text blocks matter here.
    if isinstance(result, tuple):
        result = result[0]
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return "\n".join(getattr(b, "text", str(b)) for b in result or [])


async def run(calls: list[dict]) -> None:
    mcp = FastMCP("smoke")
    register_tools(mcp, BridgeContext())
    for call in calls:
        args = dict(call)
        name = args.pop("tool")
        print(f"===== {name} {json.dumps(args, ensure_ascii=False)[:160]}", flush=True)
        t0 = time.perf_counter()
        try:
            print(_text(await mcp.call_tool(name, args)), flush=True)
        except Exception as exc:  # report and keep going
            print(f"EXCEPTION {type(exc).__name__}: {exc}", flush=True)
        print(f"----- {time.perf_counter() - t0:.2f} s", flush=True)


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.exit("usage: python -m src.packet_tracer_mcp.devtools.live_smoke <calls.json> [...]")
    for path in argv:
        calls = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        asyncio.run(run(calls))


if __name__ == "__main__":
    main()
