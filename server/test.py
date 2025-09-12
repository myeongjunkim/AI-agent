
from fastmcp import Client, FastMCP
import asyncio
from pathlib import Path



client = Client({
  "mcpServers": {
      "websearch-mcp": {
        "command": "python",
        "args": ["../mcp/websearch-mcp/app/main.py"]
      }
  }
})


async def main() -> None:
    async with client :
        print(await client.ping())

 

if __name__ == "__main__":
    asyncio.run(main())