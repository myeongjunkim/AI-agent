import asyncio

from app.providers.google_news_rss import GoogleNewsRSSProvider
from app.tools.schema import BaseSearchResponse

async def main():
    
    provider = GoogleNewsRSSProvider()
    items = await provider.search(query="삼성전자", limit=20)
    response = BaseSearchResponse(
        query="삼성전자",
        results=items
    )
    return response.model_dump()

asyncio.run(main())