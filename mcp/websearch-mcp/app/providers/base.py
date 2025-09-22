from __future__ import annotations

from typing import Protocol, Literal, List, Optional, TypedDict


Channel = Literal["web", "news", "blog"]


class SearchItem(TypedDict, total=False):
    title: str
    url: str
    snippet: Optional[str]
    published_at: Optional[str]
    provider: Optional[str]   
    source: Optional[str]
    channel: Channel
    language: Optional[str]
    thumbnail: Optional[str]
    score: Optional[float]


class Provider(Protocol):
    name: str
    channel: Channel

    async def search(
        self,
        query: str,
        *,
        lang: str,
        region: str,
        time_range: str,
        limit: int,
    ) -> List[SearchItem]: ...


