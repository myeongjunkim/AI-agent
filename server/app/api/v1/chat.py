from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app._core.config import settings
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from app.client.agent import MCPAgent
from langchain_mcp_adapters.client import MultiServerMCPClient
import json

router = APIRouter(prefix="/v1/chat", tags=["chat"])

@router.post("/")
async def chat(request) -> JSONResponse:
    with open("mcp.json", "r") as f:
        mcp_config = json.load(f)
        mcp = MultiServerMCPClient(mcp_config)
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=SecretStr(settings.OPENAI_API_KEY),
        base_url=settings.BASE_URL,
    )
    agent = MCPAgent(llm, mcp)
    response = await agent.chat(request)
    return response

    