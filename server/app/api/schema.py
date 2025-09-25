from pydantic import BaseModel
from typing import List



class ChatRequest(BaseModel):
    query: str


## 변경 예정
class ChatResponse(BaseModel):
    query: str
    answer: str
    result: dict
    mcp_result: List[dict]
    key_info: List[dict]


class SearchRequest(BaseModel):
    query: str



class SearchResponse(BaseModel):
    status: str
    query: str
    expanded_query: dict
    statistics: dict
    documents: list[dict]
    timestamp: str
    