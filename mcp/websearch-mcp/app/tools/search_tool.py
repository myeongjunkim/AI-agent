from __future__ import annotations

from typing import List
import asyncio

from .base import BaseTool
from ..providers.base import SearchItem
from ..providers.google_cse import GoogleCSEProvider
from ..providers.google_news_rss import GoogleNewsRSSProvider
from ..providers.naver_openapi import NaverBlogProvider, NaverNewsProvider, NaverWebProvider
from ..utils.rank import deduplicate, sort_items
from ..config import settings

from ..providers.enums import  Channel

from app.tools.schema import BaseSearchRequest, BaseSearchResponse, SearchRequest, SearchResponse




class SearchTool(BaseTool):
    def __init__(self) -> None:
        self.naver_web_provider = NaverWebProvider(settings.NAVER_CLIENT_ID, settings.NAVER_CLIENT_SECRET)
        self.naver_news_provider = NaverNewsProvider(settings.NAVER_CLIENT_ID, settings.NAVER_CLIENT_SECRET)
        self.naver_blog_provider = NaverBlogProvider(settings.NAVER_CLIENT_ID, settings.NAVER_CLIENT_SECRET)
        self.google_cse_provider = GoogleCSEProvider(settings.GOOGLE_SEARCH_API_KEY, settings.GOOGLE_CX_ID)
        self.google_news_rss_provider = GoogleNewsRSSProvider()

    async def execute(self, request: SearchRequest) -> SearchResponse:
        channels = request.channels or [Channel.news, Channel.web]
        payload = {
            "query": request.query,
            "lang": request.lang,
            "region": request.region,
            "time_range": request.time_range,
            "limit": request.limit_per_channel
        }

        tasks = []
        for channel in channels:
            if channel == Channel.web:
                tasks.append(self.naver_web_provider.search(**payload))
                tasks.append(self.google_cse_provider.search(**payload))
            elif channel == Channel.news:
                tasks.append(self.google_news_rss_provider.search(**payload))
                tasks.append(self.naver_news_provider.search(**payload))
            elif channel == Channel.blog:
                tasks.append(self.naver_blog_provider.search(**payload))
            else:
                raise ValueError(f"Invalid channel: {channel}")

        results = await asyncio.gather(*tasks, return_exceptions=True)
        collected: List[SearchItem] = []
        for result in results:
            if isinstance(result, Exception):
                continue
            collected.extend(result)

        deduplicated = deduplicate(collected)
        sorted_items = sort_items(deduplicated)
        # result = [SearchItemModel.model_validate(item) for item in sorted_items]
        
        return SearchResponse(
            query=request.query,
            normalized_query=request.query,
            providers_used=channels,
            items=result,
            stats={},
            errors=[],
            raw=None
        )
       


class GoogleNewsRSSSearchTool(BaseTool):
    def __init__(self) -> None:
        self.google_news_rss_provider = GoogleNewsRSSProvider()

    async def execute(self, request: BaseSearchRequest) -> BaseSearchResponse:
        search_items = await self.google_news_rss_provider.search(request.query, request.limit)
        return BaseSearchResponse(
            query=request.query,
            results=search_items
        )