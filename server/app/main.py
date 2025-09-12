from fastapi import FastAPI
from app.api.router import api_router
from contextlib import asynccontextmanager
from typing import AsyncIterator
from fastmcp import Client
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = {
        "mcpServers": {
                "websearch-mcp": {
                "command": "python",
                "args": ["../mcp/websearch-mcp/app/main.py"],
            }
        }
    }
    mcp_client = Client(config)
    async with mcp_client:
        tools = await mcp_client.list_tools()
        print(tools)
        yield
        await mcp_client.close()


app = FastAPI(title="AI Agent Server", version="0.1.0", lifespan=lifespan)
app.include_router(api_router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)