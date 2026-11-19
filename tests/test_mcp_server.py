import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FX = Path(__file__).parent / "fixtures" / "py_app"


async def _call():
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "migratelens.mcp_server", str(FX)]
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)
            inv = await session.call_tool("detect_aws", {})
            escape = await session.call_tool("read_file", {"path": "../../../etc/hosts"})
            return tools, inv, escape


def test_mcp_exposes_only_read_only_tools_and_blocks_escape():
    tools, inv, escape = asyncio.run(_call())
    assert tools == ["detect_aws", "list_files", "map_service", "read_file"]
    services = {s["service"] for s in json.loads(inv.content[0].text)["services"]}
    assert {"S3", "SQS"} <= services
    assert escape.is_error  # path traversal refused by the tool
