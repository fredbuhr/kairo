import asyncio

from mcp import Client
from mcp.server import MCPServer

from nevolium_worker.tool_runtime import _result_payload


async def main() -> None:
    server = MCPServer("Nevolium MCP contract")

    @server.tool()
    def echo(message: str) -> dict[str, str]:
        """Echo a message without side effects."""
        return {"message": message}

    async with Client(server) as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools.tools]
        assert names == ["echo"], names
        result = await client.call_tool("echo", {"message": "nevolium"})
        payload = _result_payload(result)
        assert payload.get("isError", payload.get("is_error", False)) is False
        structured = payload.get("structuredContent") or payload.get("structured_content")
        assert structured == {"message": "nevolium"}, payload

    print("MCP tool contract PASS")


if __name__ == "__main__":
    asyncio.run(main())
