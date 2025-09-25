from fastapi import APIRouter
from app._core.config import settings
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from app.client.agent import MCPAgent
from langchain_mcp_adapters.client import MultiServerMCPClient
import json

from app.api.schema import ChatResponse, ChatRequest

router = APIRouter(prefix="/v1/chat", tags=["chat"])

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    with open("mcp.json", "r") as f:
        mcp_config = json.load(f)
        mcp = MultiServerMCPClient(mcp_config)
    llm = ChatOpenAI(
        model=settings.MODEL_NAME,
        api_key=SecretStr(settings.OPENAI_API_KEY),
        base_url=settings.BASE_URL,
    )
    agent = MCPAgent(llm, mcp)
    result = await agent.chat(request.query)
    
    # TOBE: 응답 확인 후 파싱하여 반영 예정
    response = ChatResponse(
        query=request.query,
        result=result,
        answer="",
        mcp_result=[],
        key_info=[]
    )

    return response

    