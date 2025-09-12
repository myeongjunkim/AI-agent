from fastmcp import FastMCP

mcp = FastMCP("Test Server")

@mcp.tool
def add(a, b):
    return a + b

if __name__ == "__main__":
    mcp.run()
