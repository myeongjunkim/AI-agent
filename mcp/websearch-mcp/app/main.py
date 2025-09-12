from fastmcp import FastMCP

mcp = FastMCP(
    name="Websearch MCP",
    instructions="Provides real-time websearch information."
)

@mcp.tool
def get_current_websearch(location: str):
    """
    Retrieves the current weather for a given location.
    :param location: The name of the city.
    :return: A summary of the current weather.
    """
    if location == "Seoul":
        return "The current weather in Seoul is sunny, 25°C."
    else:
        return "Weather information not found for this location."



if __name__ == "__main__":
    mcp.run(transport="stdio")