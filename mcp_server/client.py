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
    def __init__(self, mcp_target: str = "http://localhost:8000/mcp") -> None:
        self.mcp_target = mcp_target
        #If you want a persistent connection (for multiple api calls and better performance), uncomment the code below
        self.client = None
    
    async def __aenter__(self):
        """
        Use only if utilising the persistent connection option
        """
        self.client = Client(self.mcp_target)
        await self.client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        """
        Use only if utilising the persistent connection option
        """
        if self.client:
            await self.client.__aexit__(exc_type, exc, tb)

    async def call_tool(self, tool, args=None):
        """
        Use only if utilising the persistent connection option
        """
        if not self.client:
            raise RuntimeError("Client is not connected. Use 'async with' context.")
        return await self.client.call_tool(tool, args or {})

    # async def call_tool(self, tool: str, args: Optional[Dict[str, any]]):
    #     """Open a client session to the MCP server and call a tool."""
    #     async with Client(self.mcp_target) as client:
    #         return await client.call_tool(tool, args or {})

    async def list_tools(self):
        """Helper method to list available tools using the persistent client."""
        if not self.client:
            raise RuntimeError("Client is not connected. Use 'async with' context.")
        return await self.client.list_tools()
    
    async def default_demo(self) -> None:
        """Convenience demo: call fetch_data on the OpenAI repo."""
        result = await self.call_tool(
            "fetch_data",
            {"endpoint": "/repos/openai/openai-python"},
        )
        print("Tool result:", result)

async def _amain():
    # THIS IS THE FIX: For a one-shot command-line test, we don't need the MCPClient class.
    # We can create a temporary client directly.
    mcp_target = "http://localhost:8000/mcp"

    if len(sys.argv) < 2:
        print("Usage: python -m mcp_server.client <tool_name> ['<json_args>']")
        print("Example: python -m mcp_server.client fetch_data '{\"endpoint\":\"/users/octocat\"}'")
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
    
    # Create a temporary client for a single tool call
    async with Client(mcp_target) as client:
        result = await client.call_tool(tool, args) 
        print("Tool result:", json.dumps(dict(result.content[0]), indent=2))

if __name__ == "__main__":
    asyncio.run(_amain())




if __name__ == "__main__":
    asyncio.run(_amain())