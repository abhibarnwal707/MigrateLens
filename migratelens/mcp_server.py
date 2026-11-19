"""Read-only MCP server exposing the repo tools. Usage: python -m migratelens.mcp_server <repo>

The repo root is fixed at start-up, so a client cannot read outside it.
"""

from __future__ import annotations

import sys

from mcp.server.mcpserver import MCPServer

from migratelens.tools.toolset import make_tools


def build_server(repo_root: str) -> MCPServer:
    server = MCPServer("migratelens-repo-tools")
    for fn in make_tools(repo_root).values():
        server.tool()(fn)
    return server


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m migratelens.mcp_server <repo_path>")
    build_server(sys.argv[1]).run("stdio")


if __name__ == "__main__":
    main()
