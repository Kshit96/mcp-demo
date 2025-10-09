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

# --- Global shared app object (used by fastmcp CLI) ---
config = Config()
app = FastMCP("PublicAPIServer")

# Register tools at import time
APITool(app, base_url=config.default_api_url)


if __name__ == "__main__":
    print("[server] Running in standalone mode...")
    app.run()

"""
HOW TO RUN:
1. When you want to run it as a module using python3: python3 -m mcp_server.server    
2. When you want to run it using fastmcp cli: PYTHONPATH=. FASTMCP_LOG_LEVEL=debug fastmcp run ./mcp_server/server.py:app (to run it in stdio mode)
3. When you want to run it using fastmcp cli: PYTHONPATH=. FASTMCP_LOG_LEVEL=debug fastmcp run ./mcp_server/server.py:app --transport http --port 8000 in http mode (to run it in http mode)

HOW TO INSPECT:
After running the server successfully, you can inspect it by:
PYTHONPATH=. FASTMCP_LOG_LEVEL=debug fastmcp inspect ./mcp_server/server.py:app
"""