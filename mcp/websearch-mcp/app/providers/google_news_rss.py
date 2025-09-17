from __future__ import annotations

from typing import List
import feedparser
from feedparser import FeedParserDict
from .base import Provider, SearchItem
from ..utils.normalize import normalize_url, extract_domain, parse_date_to_iso


class GoogleNewsRSSProvider(Provider):  # type: ignore[misc]
    name = "google_news_rss"
    channel = "news"
    base_url = "https://news.google.com/rss/search"


    async def search(self, query: str, *, lang: str, region: str, time_range: str, limit: int) -> List[SearchItem]:
        # hl, gl, ceid
        hl = lang or "ko"
        gl = region or "KR"
        ceid = f"{gl}:{hl}"
        url = f"{self.base_url}?q={query}&hl={hl}&gl={gl}&ceid={ceid}"

        # feedparser는 동기식. 간단히 사용.
        feed: FeedParserDict = feedparser.parse(url)
        entries: List[FeedParserDict] = feed.get("entries", [])[:limit]
        results: List[SearchItem] = []
        for e in entries:
            link = normalize_url(e.get("link", ""))
            if not link:
                continue
            results.append(
                SearchItem(
                    title=e.get("title", ""),
                    snippet=e.get("summary", ""),
                    url=link,    
                    source=extract_domain(link),
                    provider=self.name,
                    channel=self.channel,
                    published_at=parse_date_to_iso(e.get("published")),
                    language=lang,
                )
            )
        return results




