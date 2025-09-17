from fastmcp import FastMCP
from .tools.search_tool import SearchTool
from .tools.schema import SearchRequest, SearchResponse

mcp = FastMCP(
    name="Websearch MCP",
    instructions="Provides real-time websearch information."
)


@mcp.tool
async def aggregate_search_tool(req: SearchRequest) -> dict:
    """Aggregates Google/Naver search results and returns normalized JSON for LLM summarization."""
    search_tool = SearchTool()
    response: SearchResponse = await search_tool.execute(req)
    return response.model_dump()


if __name__ == "__main__":
    mcp.run(transport="stdio")