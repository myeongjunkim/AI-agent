from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from pydantic import BaseModel, Field


class MCPServerConfig(BaseModel):
    command: str = Field(...)
    path: str = Field(...)
    env: Dict[str, str] = Field(default_factory=dict)



class MCPClient:

    def __init__(
        self,
        server_name: str,
    ) -> None:
        self._server_name = server_name
        self._config: MCPServerConfig = self._load_mcp_server_config(server_name=server_name)
        self._acm = None
        self._read_write: Optional[Tuple[Any, Any]] = None
        self._session: Optional[ClientSession] = None

    async def start(self) -> None:
        if self._session is not None:
            return
        mcp_project_path = "../mcp/websearch-mcp"

        params = StdioServerParameters(
            command=["uv", "run", "fastmcp", "run", "app/main.py"],
            cwd=mcp_project_path
        )

    async def stop(self) -> None:
        if self._acm is not None:
            await self._acm.__aexit__(None, None, None)
        self._acm = None
        self._session = None

    async def list_tools(self) -> Any:
        """List tools from the MCP server. Returns the MCP ListToolsResult object."""
        if self._session is not None:
            return await self._session.list_tools()

        params = StdioServerParameters(
            command="uv",
            args=["run", "fastmcp", "run", "app/main.py"],
            cwd="C:\\Users\\User\\dev\\AI-agent\\mcp\\websearch-mcp",
        )
        async with stdio_client(params) as (read, write):
            session = ClientSession(read, write)
            await session.initialize()
            return await session.list_tools()


    @staticmethod
    def _to_dict(obj: Any) -> Dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        dump = getattr(obj, "model_dump", None)
        if callable(dump):
            return dump()
        to_dict = getattr(obj, "dict", None)
        if callable(to_dict):
            return to_dict()
        # Fallback best-effort
        try:
            return json.loads(json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o))))
        except Exception:
            return {}

    async def list_tools_for_openai(self, *, timeout_seconds: Optional[float] = None) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI tools format for tool-calling.

        Output shape per tool:
        {"type":"function","function":{"name":...,"description":...,"parameters":{...}}}
        """
        result = await self.list_tools(timeout_seconds=timeout_seconds)
        tools_json: List[Dict[str, Any]] = []
        for t in getattr(result, "tools", []) or []:
            name = getattr(t, "name", None)
            desc = getattr(t, "description", None)
            params_schema = self._to_dict(getattr(t, "inputSchema", {}))
            if not name:
                continue
            tools_json.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc or "",
                    "parameters": params_schema or {"type": "object", "properties": {}},
                },
            })
        return tools_json


    def _load_mcp_server_config(self, server_name: str, config_filename: str = ".mcp.json") -> MCPServerConfig:
        here = Path(__file__).resolve()
        base_dir = Path(str(here.parents[2])).resolve()
        config_path = base_dir / config_filename

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        servers = cfg.get("mcpServers") or {}
        if server_name not in servers:
            raise KeyError(f"MCP server '{server_name}' not found in {config_filename}")

        mcp_config = servers[server_name]
        command = mcp_config.get("command")
        path = mcp_config.get("path")
        env = mcp_config.get("env") or {}

        return MCPServerConfig(command=command, path=path, env=env)



