from __future__ import annotations

from typing import List
from .base import Provider, SearchItem
from .schema import GoogleCSEResponse
from ..utils.http import build_async_client
from ..utils.normalize import normalize_url, extract_domain


class GoogleCSEProvider(Provider):  # type: ignore[misc]
    name = "google_cse"
    channel = "web"
    base_url = "https://www.googleapis.com/customsearch/v1"


    def __init__(self, api_key: str, cse_id: str):
        if not api_key or not cse_id:
            raise ValueError("GoogleCSEProvider requires api_key and cse_id")
        self.api_key = api_key
        self.cse_id = cse_id

    async def search(self, query: str, *, lang: str, region: str, time_range: str, limit: int) -> List[SearchItem]:
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(10, max(1, limit)),
            "safe": "off",
        }
        dr = self._map_time_range_to_google(time_range)
        if dr:
            params["dateRestrict"] = dr
        if lang and lang != "auto":
            params["hl"] = lang
        if region:
            params["gl"] = region

        async with build_async_client(lang) as client:
            resp = await client.get(self.base_url, params=params)
            if resp.status_code != 200:
                return []
            data = GoogleCSEResponse.model_validate(resp.json())
            items = data.items
            results: List[SearchItem] = []
            for it in items:
                url = normalize_url(it.link or "")
                if not url:
                    continue
                results.append(
                    {
                        "title": it.title or "",
                        "snippet": it.snippet or "",
                        "url": url,
                        "source": extract_domain(url),
                        "provider": self.name,
                        "channel": self.channel,
                        "published_at": None,
                        "language": lang,
                        "thumbnail": None,
                    }
                )
            return results


    def _map_time_range_to_google(self,date_range: str) -> str | None:
        if date_range == "24h":
            return "d1"
        if date_range == "7d":
            return "w1"
        if date_range == "30d":
            return "m1"
        return None