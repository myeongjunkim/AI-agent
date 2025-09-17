
from fastmcp import Client, FastMCP
import asyncio
from pathlib import Path



client = Client({
  "mcpServers": {
      "websearch-mcp": {
        "command": "uv",
        "args": ["uv","run", "fastmcp", "run", "../mcp/websearch-mcp/app/main.py"],
        "cwd": "../mcp/websearch-mcp"
      }
  }
})


async def main() -> None:
    async with client :
        print(await client.ping())

 

if __name__ == "__main__":
    asyncio.run(main())