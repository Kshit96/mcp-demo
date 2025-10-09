"""
client.py
----------
MCP client executing the API specific tool.
"""
from fastmcp.client import Client

async def main():
    async with Client("http://localhost:8000/mcp") as client:
        result = await client.call_tool("fetch_data", {"endpoint": "/repos/openai/openai-python"})
        print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

"""
HOW TO RUN CLIENT
1. First ensure that the MCP server is running on localhost (see server.py for instructions)
2. Then use the command 'python3 -m mcp_server.client' to run the client

The client will connect to the MCP server and invoke the tool with the right api provided and print the result in the terminal
"""