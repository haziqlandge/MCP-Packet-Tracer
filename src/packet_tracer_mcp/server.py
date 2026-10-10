"""
MCP server for Packet Tracer.

Entry point: creates the server, registers tools/resources, and starts
on streamable-http (:39000) or stdio depending on the --stdio flag.
"""

from __future__ import annotations

import argparse
import sys

# Doctor must work without initializing the MCP transport or bridge.
if sys.argv[1:2] == ["doctor"]:
    from .infrastructure.platform.doctor import main as doctor_main
    raise SystemExit(doctor_main(sys.argv[2:]))

from mcp.server.fastmcp import FastMCP

from . import __version__
from .adapters.mcp.prompt_registry import register_prompts
from .adapters.mcp.resource_registry import register_resources
from .adapters.mcp.tool_registry import register_tools
from .settings import SERVER_NAME, SERVER_INSTRUCTIONS

TRANSPORT_PORT = 39000

mcp = FastMCP(
    SERVER_NAME,
    instructions=SERVER_INSTRUCTIONS,
    host="127.0.0.1",
    port=TRANSPORT_PORT,
    stateless_http=True,
)

# Report OUR version in the handshake, not the SDK's.
#
# `create_initialization_options()` resolves the number with
# `self.version if self.version else pkg_version("mcp")`, and FastMCP does not expose
# `version` in its `__init__` nor a property for the lowlevel server, so the
# fallback always won: the server presented itself as "1.28.1" — the library —
# instead of "0.8.0". That number is the one Claude Desktop, Cursor and PacketSmith
# show in their server panel, and on top of that it changed on its own whenever the
# dependency was updated.
#
# `_mcp_server` is private and there is no public alternative; it is guarded so that
# a future SDK version that renames it degrades to the old behavior instead of
# breaking startup, which is the one thing that cannot be allowed here.
_lowlevel = getattr(mcp, "_mcp_server", None)
if _lowlevel is not None:
    _lowlevel.version = __version__

register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)


def main(argv: list[str] | None = None):
    """Run diagnostics or start the MCP transport."""
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["doctor"]:
        from .infrastructure.platform.doctor import main as doctor_main
        raise SystemExit(doctor_main(argv[1:]))
    parser = argparse.ArgumentParser(description="Packet Tracer MCP server")
    parser.add_argument("--stdio", action="store_true", help="Use MCP standard input/output")
    parser.add_argument("--port", type=int, default=TRANSPORT_PORT,
                        help="MCP HTTP port (default: 39000; bridge stays on 54321)")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    mcp.settings.port = args.port
    mcp.run(transport="stdio" if args.stdio else "streamable-http")


if __name__ == "__main__":
    main()
