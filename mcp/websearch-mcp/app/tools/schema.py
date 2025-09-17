from __future__ import annotations

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


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


class SearchItemModel(BaseModel):
    id: int
    title: str
    snippet: str
    url: str
    source: str
    provider: str
    channel: str
    published_at: Optional[str] = None
    language: Optional[str] = None
    thumbnail: Optional[str] = None
    score: Optional[float] = None


class SearchResponse(BaseModel):
    query: str
    normalized_query: str
    providers_used: List[str]
    items: List[Any]
    stats: Dict[str, object]
    errors: List[ErrorInfo]
    raw: Optional[List[dict]] = None


