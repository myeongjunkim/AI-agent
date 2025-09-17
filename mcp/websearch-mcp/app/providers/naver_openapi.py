from __future__ import annotations

from typing import List
from .base import Provider, SearchItem
from .schema import NaverResponse
from ..utils.http import build_async_client
from ..utils.normalize import normalize_url, extract_domain, parse_date_to_iso


class NaverWebProvider:  # type: ignore[misc]
    name = "naver_web"
    channel = "web"
    base_url = "https://openapi.naver.com/v1/search/webkr.json"

    def __init__(self, client_id: str, client_secret: str):
        if not client_id or not client_secret:
            raise ValueError("NaverWebProvider requires client_id and client_secret")
        self.client_id = client_id
        self.client_secret = client_secret

    async def search(self, query: str, *, lang: str, region: str, time_range: str, limit: int) -> List[SearchItem]:
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {"query": query, "display": min(50, max(1, limit)), "start": 1, "sort": "sim"}
        async with build_async_client(lang) as client:
            resp = await client.get(self.base_url, headers=headers, params=params)
        if resp.status_code != 200:
            return []
        data = NaverResponse.model_validate(resp.json())
        items = data.items
        results: List[SearchItem] = []
        for it in items:
            url = normalize_url(it.link or "")
            if not url:
                continue
            results.append(
                {
                    "title": it.title or "",
                    "snippet": it.description or "",
                    "url": url,
                    "source": extract_domain(url),
                    "provider": self.name,
                    "channel": self.channel,
                    "published_at": None,
                    "language": lang,
                }
            )
        return results


class NaverNewsProvider:  # type: ignore[misc]
    name = "naver_news"
    channel = "news"
    base_url = "https://openapi.naver.com/v1/search/news.json"


    def __init__(self, client_id: str, client_secret: str):
        if not client_id or not client_secret:
            raise ValueError("NaverNewsProvider requires client_id and client_secret")
        self.client_id = client_id
        self.client_secret = client_secret

    async def search(self, query: str, *, lang: str, region: str, time_range: str, limit: int) -> List[SearchItem]:
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {"query": query, "display": min(50, max(1, limit)), "start": 1, "sort": "date"}
        async with build_async_client(lang) as client:
            resp = await client.get(self.base_url, headers=headers, params=params)
        if resp.status_code != 200:
            return []
        data = NaverResponse.model_validate(resp.json())
        items = data.items
        results: List[SearchItem] = []
        for it in items:
            url = normalize_url(it.link or "")
            if not url:
                continue
            results.append(
                {
                    "title": it.title or "",
                    "snippet": it.description or "",
                    "url": url,
                    "source": extract_domain(url),
                    "provider": self.name,
                    "channel": self.channel,
                    "published_at": parse_date_to_iso(it.pubDate),
                    "language": lang,
                }
            )
        return results


class NaverBlogProvider:  # type: ignore[misc]
    name = "naver_blog"
    channel = "blog"
    base_url = "https://openapi.naver.com/v1/search/blog.json"


    def __init__(self, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret:
            raise ValueError("NaverBlogProvider requires client_id and client_secret")
        self.client_id = client_id
        self.client_secret = client_secret


    async def search(self, query: str, *, lang: str, region: str, time_range: str, limit: int) -> List[SearchItem]:
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {"query": query, "display": min(50, max(1, limit)), "start": 1, "sort": "date"}

        async with build_async_client(lang) as client:
            resp = await client.get(self.base_url, headers=headers, params=params)
        if resp.status_code != 200:
            return []
            
        data = NaverResponse.model_validate(resp.json())
        items = data.items
        results: List[SearchItem] = []
        for it in items:
            url = normalize_url(it.link or "")
            if not url:
                continue
            results.append(
                {
                    "title": it.title or "",
                    "snippet": it.description or "",
                    "url": url,
                    "source": extract_domain(url),
                    "provider": self.name,
                    "channel": self.channel,
                    "published_at": parse_date_to_iso(it.postdate),
                    "language": lang,
                }
            )
        return results



