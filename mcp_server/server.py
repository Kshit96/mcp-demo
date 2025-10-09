"""
server.py
----------
MCP server exposing one OOP-style API Tool.
"""

from fastmcp import FastMCP
from mcp_server.core.config import Config
from mcp_server.tools.api_tool import APITool
# import sys, os
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))

def create_app() -> FastMCP:
    config = Config()
    app = FastMCP("MCPDemoServer")

    # Register all tools
    APITool(app, base_url=config.default_api_url)

    return app


if __name__ == "__main__":
    print("[server] Running in standalone mode...")
    app = create_app()
    app.run()

"""
HOW TO RUN:
1. When you want to run it as a module using python3: python3 -m mcp_server.server    
2. When you want to run it using fastmcp cli: PYTHONPATH=. FASTMCP_LOG_LEVEL=debug fastmcp run ./mcp_server/server.py:create_app (to run it in stdio mode)
3. When you want to run it using fastmcp cli: PYTHONPATH=. FASTMCP_LOG_LEVEL=debug fastmcp run ./mcp_server/server.py:create_app --transport http --port 8000 (to run it in http mode)
4. When you want to run the server in dev mode: PYTHONPATH=. FASTMCP_LOG_LEVEL=debug fastmcp dev ./mcp_server/server.py:create_app

NOTE: fastmcp run ignores the main function, hence we use the factory function call directly to return an app

HOW TO INSPECT:
After running the server successfully, you can inspect it by:
PYTHONPATH=. FASTMCP_LOG_LEVEL=debug fastmcp inspect ./mcp_server/server.py:app
"""