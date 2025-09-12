from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.client.llm import LLMClient, LLMClientParams
from app._core.config import settings
from app.client.mcp import MCPClient

router = APIRouter(prefix="/v1/chat", tags=["chat"])

@router.post("/")
async def chat(request: Request) -> JSONResponse:
    # 1) MCP tools 준비 (영속 세션이 있으면 사용, 없으면 요청 단위 생성)
    # mcp = request.app.state.mcp_persistent if hasattr(request.app.state, "mcp_persistent") else MCPClient("websearch-mcp")
    # tools = await mcp.list_tools_for_openai()

    websearch_mcp = MCPClient("websearch-mcp")
    await websearch_mcp.start()   

    params = LLMClientParams(model_name=settings.MODEL_NAME, api_key=settings.OPENAI_API_KEY, tools=[])
    llm = LLMClient(params=params)

    query = await request.body()
    response = llm.chat(query=query)

    return JSONResponse(content=jsonable_encoder(response))
