"""
client.py
----------
MCP client executing the API specific tool.

HOW TO RUN CLIENT
1. First ensure that the MCP server is running on localhost (see server.py for instructions)
2. Then use the command 'python3 -m mcp_server.client' to run the client

The client will connect to the MCP server and invoke the tool with the right api provided and print the result in the terminal
"""
import asyncio
import json
import sys
from typing import Dict, Optional
from fastmcp.client import Client

class MCPClient:
    """Minimal class wrapper around the FastMCP Client (HTTP transport)."""
    def __init__(self, url: str = "http://localhost:8000/mcp") -> None:
        self.url = url
        #If you want a persistent connection (for multiple api calls and better performance), uncomment the code below
        #self.client = None
    
    # async def __aenter__(self):
    #     """
    #     Use only if utilising the persistent connection option
    #     """
    #     self.client = Client(self.url)
    #     await self.client.__aenter__()
    #     return self
    
    # async def __aexit__(self, exc_type, exc, tb):
    #     """
    #     Use only if utilising the persistent connection option
    #     """
    #     if self.client:
    #         await self.client.__aexit__(exc_type, exc, tb)

    # async def call_tool(self, tool, args=None):
    #     """
    #     Use only if utilising the persistent connection option
    #     """
    #     return await self.client.call_tool(tool, args or {})

    async def call_tool(self, tool: str, args: Optional[Dict[str, any]]):
        """Open a client session to the MCP server and call a tool."""
        async with Client(self.url) as client:
            return await client.call_tool(tool, args or {})
    
    async def default_demo(self) -> None:
        """Convenience demo: call fetch_data on the OpenAI repo."""
        result = await self.call_tool(
            "fetch_data",
            {"endpoint": "/repos/openai/openai-python"},
        )
        print("Tool result:", result)

async def _amain():
    client = MCPClient(url="http://localhost:8000/mcp")

    if len(sys.argv) == 1:
        await client.default_demo()
        return
    
    tool = sys.argv[1]

    if len(sys.argv) > 2:
        try:
            args = json.loads(sys.argv[2])
        except json.JSONDecodeError:
            print("Second argument must be valid JSON (e.g. '{\"endpoint\":\"/users/octocat\"}')")
            sys.exit(1)
    else:
        args = {}

    #TOOL CALLING - Persistent connection
    #Use the version below for persistent connection version of the MCP Client to make multiple calls using the same connection
    # async with PersistentMCPClient() as mcp:
        # result1 = await mcp.call_tool("fetch_data", {"endpoint": "/users/octocat"})
        # result2 = await mcp.call_tool("fetch_data", {"endpoint": "/repos/openai/openai-python"})
    
    #TOOL CALLING - One connection per tool call
    #Otherwise use this for one connection per tool call
    result = await client.call_tool(tool, args) 
    print("Tool result:", result)




if __name__ == "__main__":
    asyncio.run(_amain())