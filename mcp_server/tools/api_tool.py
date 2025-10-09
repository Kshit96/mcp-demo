import httpx
from fastmcp import FastMCP

class APITool:
    """
    A simple OOP-based API Tool for mCP.
    Uses httpx to call public APIs safely
    """

    def __init__(self, app: FastMCP, base_url) -> None:
        self.app = app
        self.base_url = base_url
        self._register_tool()
    
    def _register_tool(self):
        @self.app.tool

        def fetch_data(endpoint: str):
            """
            Fetch data from a public API endpoint relative to base_url.
            Example: endpoint="/repos/openai/openai-python"
            """
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            try:
                with httpx.Client(timeout=10) as client:
                    r = client.get(url)
                    data = r.json()
                    return {"status": r.status_code, "data": data}
            except Exception as e:
                return {"error": str(e)}