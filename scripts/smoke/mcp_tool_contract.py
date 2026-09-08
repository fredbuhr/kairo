import asyncio

from mcp import Client
from mcp.server import MCPServer

from kairo_worker.tool_runtime import (
    _live_tool_schema_hash,
    _require_live_tool_contract,
    _result_payload,
)


async def main() -> None:
    server = MCPServer("KAIRO MCP contract")

    @server.tool()
    def echo(message: str) -> dict[str, str]:
        """Echo a message without side effects."""
        return {"message": message}

    async with Client(server) as client:
        tools = await client.list_tools()
        names = [tool.name for tool in tools.tools]
        assert names == ["echo"], names

        live_hash = _live_tool_schema_hash(tools.tools[0])
        assert len(live_hash) == 64, live_hash
        bound = _require_live_tool_contract(
            list(tools.tools), remote_name="echo", expected_schema_hash=live_hash
        )
        assert bound.name == "echo", bound

        try:
            _require_live_tool_contract(
                list(tools.tools), remote_name="echo", expected_schema_hash="0" * 64
            )
        except RuntimeError as exc:
            assert "schema drifted" in str(exc), exc
        else:
            raise AssertionError("KAIRO accepted a live MCP schema that differs from the Task snapshot")

        try:
            _require_live_tool_contract(
                list(tools.tools), remote_name="missing", expected_schema_hash=live_hash
            )
        except RuntimeError as exc:
            assert "disappeared" in str(exc), exc
        else:
            raise AssertionError("KAIRO accepted an MCP tool missing from the live server catalog")

        result = await client.call_tool("echo", {"message": "kairo"})
        payload = _result_payload(result)
        assert payload.get("isError", payload.get("is_error", False)) is False
        structured = payload.get("structuredContent") or payload.get("structured_content")
        assert structured == {"message": "kairo"}, payload

    print("MCP tool contract PASS: live schema matches are accepted and drift/disappearance fail closed")


if __name__ == "__main__":
    asyncio.run(main())
