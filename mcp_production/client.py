import asyncio
import json
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_tool(session: ClientSession, tool_name: str, args: dict[str, Any]) -> Any:
    result = await session.call_tool(tool_name, args)
    structured_content = getattr(result, "structuredContent", None)
    if structured_content is not None:
        return structured_content

    decoded_blocks: list[Any] = []
    for block in result.content:
        text = getattr(block, "text", None)
        if text is None:
            decoded_blocks.append(
                block.model_dump() if hasattr(block, "model_dump") else str(block)
            )
            continue

        try:
            decoded_blocks.append(json.loads(text))
        except json.JSONDecodeError:
            decoded_blocks.append(text)

    return decoded_blocks[0] if len(decoded_blocks) == 1 else decoded_blocks


async def main() -> None:
    token = os.getenv("MCP_API_TOKEN", "")
    if not token:
        raise ValueError("Set MCP_API_TOKEN before running client.py")

    server_params = StdioServerParameters(
        command="python3",
        args=["mcp_production/server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools.tools])

            health = await call_tool(session, "healthcheck", {})
            print("healthcheck:", json.dumps(health, indent=2))

            customer_payload = {
                "name": "Rohin Example",
                "email": "rohin@example.com",
                "status": "active",
            }
            upsert_result = await call_tool(
                session,
                "upsert_customer",
                {"customer": customer_payload, "token": token},
            )
            print("upsert_customer:", json.dumps(upsert_result, indent=2))

            customers = await call_tool(
                session,
                "list_customers",
                {"limit": 10, "token": token},
            )
            print("list_customers:", json.dumps(customers, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
