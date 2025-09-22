from __future__ import annotations

from typing import Dict, List, Optional, Any
from app.providers.base import SearchItem
from pydantic import BaseModel, Field


class BaseSearchRequest(BaseModel):
    query: str
    limit: int = 50
    
class SearchRequest(BaseModel):
    query: str
    channels: List[str] = Field(default_factory=lambda: ["news", "web"])  # news 우선
    limit_per_channel: int = 5
    time_range: str = "7d"  # 24h | 7d | 30d | any
    lang: str = "ko"
    region: str = "KR"
    providers_override: Optional[Dict[str, List[str]]] = None
    include_raw: bool = False


class ErrorInfo(BaseModel):
    provider: str
    message: str


class BaseSearchItem(BaseModel):
    title: str
    url: str
    published_at: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    normalized_query: str
    providers_used: List[str]
    items: List[Any]
    stats: Dict[str, object]
    errors: List[ErrorInfo]
    raw: Optional[List[dict]] = None


class BaseSearchResponse(BaseModel):
    query: str
    results: List[SearchItem]
