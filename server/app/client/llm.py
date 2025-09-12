
from typing import Optional
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI

from pydantic import BaseModel

# basemodel
class LLMClientParams(BaseModel):
    model_name: str
    api_key: str
    base_url: str | None = None
    tools: Optional[list] = None


class LLMClient:
    def __init__(self, params: LLMClientParams) -> None:
        self._chat = ChatOpenAI(
            model=params.model_name,
            api_key=params.api_key,
            base_url=params.base_url,
        )
        # LangChain OpenAI tool-calling: pass tools at invoke time; keep for convenience
        self._tools = params.tools or []

    def chat(self, query: str, tools: Optional[list] = None) -> BaseMessage:
        messages = [HumanMessage(content=query)]
        selected_tools = tools if tools is not None else self._tools
        if selected_tools:
            return self._chat.invoke(messages, tools=selected_tools)
        return self._chat.invoke(messages)