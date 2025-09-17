import asyncio

from app.tools.search_tool import SearchTool
from app.tools.schema import SearchRequest

async def main():

    req = SearchRequest(
        query="삼성전자 실적"           ,
        channels=["news","web"],
        limit_per_channel=3,
        time_range="7d",
        lang="ko",
        region="KR",
        include_raw=False
    )
    search_tool = SearchTool()
    response = await search_tool.execute(req)
    print(response.model_dump())


asyncio.run(main())