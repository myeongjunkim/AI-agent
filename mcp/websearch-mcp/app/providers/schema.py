from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class GoogleCSEItem(BaseModel):
    kind: Optional[str] = None
    title: Optional[str] = None
    htmlTitle: Optional[str] = None
    link: Optional[str] = None
    displayLink: Optional[str] = None
    snippet: Optional[str] = None
    htmlSnippet: Optional[str] = None
    cacheId: Optional[str] = None
    formattedUrl: Optional[str] = None
    htmlFormattedUrl: Optional[str] = None
    pagemap: Optional[dict[str, Any]] = None


class GoogleCSEResponse(BaseModel):
    kind: Optional[str] = None
    items: List[GoogleCSEItem] = Field(default_factory=list)


class NaverItem(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    link: Optional[str] = None
    originallink: Optional[str] = None
    pubDate: Optional[str] = None
    postdate: Optional[str] = None


class NaverResponse(BaseModel):
    lastBuildDate: Optional[str] = None
    total: Optional[int] = None
    start: Optional[int] = None
    display: Optional[int] = None
    items: List[NaverItem] = Field(default_factory=list)


