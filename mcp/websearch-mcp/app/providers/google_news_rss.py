from typing import List
import feedparser
from feedparser import FeedParserDict
from .base import SearchItem
from urllib.parse import urlencode
import email.utils
from typing import Optional


class GoogleNewsRSSProvider:
    name = "google_news_rss"
    channel = "news"
    base_url = "https://news.google.com/rss/search"


    async def search(self, query: str, limit: int = 100) -> List[SearchItem]:
        """
        Google News RSS 피드를 파싱하여 검색 결과를 반환합니다.

        Args:
            query: 검색 쿼리
            limit: 검색 결과 개수

        Returns:
            List[SearchItem]: 검색 결과
        """
 

        params = {
            'q': query, 
            'hl': 'ko', 
            'gl': 'KR', 
            'ceid': "KR:ko",
        }
        encoded_params = urlencode(params)
        url = f"{self.base_url}?{encoded_params}"

        # feedparser는 동기식. 간단히 사용.
        feed: FeedParserDict = feedparser.parse(url)
        results: List[SearchItem] = []
        
        for item in feed.get("entries", [])[:limit]:
            results.append(SearchItem(
                title=item.get("title", ""),
                url=item.get("link", ""),
                published_at=self._parse_published_date(item.get("published", "")) or ""
            ))
        
        return results


    def _parse_published_date(self, date_str: str) -> Optional[str]:
        """
        RFC 2822 형식의 날짜를 ISO 8601 형식으로 변환합니다.
        
        Args:
            date_str: RFC 2822 형식의 날짜 문자열
            예: "Thu, 18 Sep 2025 03:57:48 GMT"
        
        Returns:
            Optional[str]: ISO 8601 형식의 날짜 문자열 또는 None (파싱 실패시)
            예: "2025-09-18T03:57:48+00:00"
        """
        if not date_str:
            return None
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_str)
            return parsed_date.isoformat()
        except (ValueError, TypeError):
            return None




