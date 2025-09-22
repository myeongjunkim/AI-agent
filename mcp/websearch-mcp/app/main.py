from app.providers.google_news_rss import GoogleNewsRSSProvider
from fastmcp import FastMCP
from app.tools.schema import BaseSearchRequest, BaseSearchResponse

mcp = FastMCP(
    name="Websearch MCP",
    instructions="Provides real-time websearch information."
)



@mcp.tool
async def google_news_rss_search_tool(req: BaseSearchRequest) -> dict:
    """Aggregates Google News RSS search results and returns normalized JSON for LLM summarization."""
    provider = GoogleNewsRSSProvider()
    items = await provider.search(req.query, req.limit)
    response = BaseSearchResponse(
        query=req.query,
        results=items
    )
    return response.model_dump()


if __name__ == "__main__":
    mcp.run(transport="stdio")