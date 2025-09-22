from fastmcp import FastMCP


mcp = FastMCP(
    name="Example MCP", 
    instructions="Provides example information."
)

@mcp.tool
async def example_tool(req: str) -> str:
    return "Hello from example-mcp!"




if __name__ == "__main__":
    mcp.run(transport="stdio")
