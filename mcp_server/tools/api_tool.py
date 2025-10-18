from typing import Optional
import httpx
from fastmcp import FastMCP

class APITool:
    """
    A simple OOP-based API Tool for mCP.
    Uses httpx to call public APIs safely
    """

    def __init__(self, app: FastMCP) -> None:
        self.app = app
        self._register_tool()
    
    def _to_int(self, name: str, value):
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        raise ValueError(f"'{name}' must be an integer")
    
    def _register_tool(self):
        @self.app.tool
        def fetch_data(
            endpoint: str,
            params: dict | None = None,
            headers: dict | None = None,
            method: str = "GET",
            body: dict | str | None = None,
        ):
            """
            Fetch data from any public API endpoint with optional headers and query/body parameters.

            Args:
            endpoint (str): Absolute URL (e.g. "https://meowfacts.herokuapp.com/").
            params (dict, optional): Query parameters to append to the URL.
            headers (dict, optional): HTTP headers to include (no secrets!).
            method (str): HTTP method ("GET", "POST", "PUT", "DELETE", ...).  Defaults to GET.
            body (dict | str, optional): Request body for non-GET methods.
                                        If dict → sent as JSON; if str → sent as raw text.

            Returns:
            dict: {
                "status": int,
                "url": str,
                "method": str,
                "query": dict,
                "headers": dict,
                "data": any | str,     # JSON if possible else text
            }
            """
            try:
                qp = {k: v for k, v in (params or {}).items() if v is not None}
                hdrs = {k: v for k, v in (headers or {}).items() if v is not None}

                method_u = method.upper().strip()
                allowed = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                if method_u not in allowed:
                    return {"error": f"Unsupported HTTP method '{method}'. Allowed: {sorted(allowed)}"}

                with httpx.Client(timeout=10) as client:
                    if method_u == "GET":
                        r = client.get(endpoint, params=qp, headers=hdrs)
                    elif method_u == "POST":
                        r = client.post(endpoint, params=qp, headers=hdrs, json=body if isinstance(body, dict) else None, data=body if isinstance(body, str) else None)
                    elif method_u == "PUT":
                        r = client.put(endpoint, params=qp, headers=hdrs, json=body if isinstance(body, dict) else None, data=body if isinstance(body, str) else None)
                    elif method_u == "PATCH":
                        r = client.patch(endpoint, params=qp, headers=hdrs, json=body if isinstance(body, dict) else None, data=body if isinstance(body, str) else None)
                    elif method_u == "DELETE":
                        r = client.delete(endpoint, params=qp, headers=hdrs)
                    elif method_u == "HEAD":
                        r = client.head(endpoint, params=qp, headers=hdrs)
                    elif method_u == "OPTIONS":
                        r = client.options(endpoint, params=qp, headers=hdrs)
                    else:
                        return {"error": f"Unsupported method '{method_u}'"}

                    # Safely parse JSON or return text
                    try:
                        body_out = r.json()
                    except Exception:
                        body_out = r.text

                    return {
                        "status": r.status_code,
                        "url": str(r.url),
                        "method": method_u,
                        "query": qp,
                        "headers": hdrs,
                        "data": body_out,
                    }
            except Exception as e:
                return {"error": str(e)}