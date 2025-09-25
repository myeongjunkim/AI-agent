
import httpx
from typing import Dict
from app.config import settings



def default_headers(lang: str) -> Dict[str, str]:
    language = lang or settings.DEFAULT_LANG
    return {
        "User-Agent": "websearch-mcp/0.1 (+https://example.local)",
        "Accept": "application/json, text/html, application/rss+xml;q=0.9, */*;q=0.8",
        "Accept-Language": language,
    }


def build_async_client(lang: str) -> httpx.AsyncClient:
    timeout = httpx.Timeout(settings.TIMEOUT_SECONDS)
    return httpx.AsyncClient(timeout=timeout, headers=default_headers(lang), follow_redirects=True)



