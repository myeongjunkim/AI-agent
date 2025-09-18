from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient  # type: ignore
from langchain_core.messages import SystemMessage
from langgraph.graph.state import RunnableConfig
from langgraph.prebuilt import create_react_agent
from langfuse.langchain import CallbackHandler
import os
from app._core.config import settings
from datetime import datetime

class MCPAgent:

    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = f"""
        현재 시간은 {time} 입니다.
        
        # MCP Agent Workflow

        당신은 MCP 전문가 챗봇입니다.

        ## 워크플로우

        1. 사용자의 질문을 이해한다.
        2. 적합한 MCP Tool을 선택한다.
        3. Tool을 호출하고 결과를 가져온다.
        4. 결과를 종합하여 최종 답변을 markdown 형식으로 작성한다.

        말투는 친절하게 유지하고, 필요한 경우 간단한 예시를 들어 설명하세요.
    
    """

    def __init__(self, llm: ChatOpenAI, mcp: MultiServerMCPClient) -> None:
        self.llm = llm
        self.mcp = mcp

        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
        os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)
        self.langfuse_handler = CallbackHandler()

    async def chat(self, query: str):
        tools = await self.mcp.get_tools()
        prompt = SystemMessage(content=self.prompt)
        agent = create_react_agent(self.llm, tools, prompt=prompt)
        config = RunnableConfig(callbacks=[self.langfuse_handler])
        return await agent.ainvoke({"messages": query}, config=config)

    

