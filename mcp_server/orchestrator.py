"""
mcp_server/orchestrator.py
--------------------------
Embedding router + RAG over Postgres-backed API catalog.
If similarity < threshold  → answer directly.
If similarity ≥ threshold → expose retrieved API cards + allow tool call.

Run: PYTHONPATH=. python3 -m mcp_server.orchestrator
"""

from __future__ import annotations
import os
import asyncio
import pprint
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
import psycopg2  # pip install psycopg[binary]
from mcp_server.client import MCPClient  # your wrapper that exposes list_tools()/call_tool()
from pathlib import Path


# ---------- Embedding + Retrieval ----------

def embed_query(text: str) -> List[float]:
    """Return an embedding vector using Gemini embeddings."""
    r = genai.embed_content(model="text-embedding-004", content=text)
    return r["embedding"]  # list[float]


def retrieve_api_candidates(pg_dsn: str, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve top-K API rows from Postgres using pgvector.
    Expected table schema (example):
      public_apis(id, name, content_for_embedding, embedding, url, params_description, response_shape)
    """
    sql = """
    SELECT id, name, url, params_description, response_shape, content_for_embedding,
           1 - (embedding <#> %s::vector) AS cosine_sim
    FROM public_apis
    ORDER BY embedding <-> %s::vector
    LIMIT %s;
    """
    with psycopg2.connect(pg_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (query_embedding, query_embedding, k))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return [dict(zip(cols, row)) for row in rows]


def make_api_cards(cands: List[Dict[str, Any]]) -> str:
    """Render compact API cards for the prompt."""
    lines = []
    for i, c in enumerate(cands, 1):
        lines.append(
f"""{i}) {c['name']}
   Base URL: {c['url']}
   Param hints: {c.get('params_description') or '—'}
   Response: {c.get('response_shape') or '—'}"""
        )
    return "\n".join(lines)


def endpoint_allowed(endpoint: str, candidates: List[Dict[str, Any]]) -> bool:
    """Simple allowlist: endpoint must start with one of the retrieved base URLs."""
    return any(isinstance(c.get("url"), str) and endpoint.startswith(c["url"]) for c in candidates)


# ---------- MCP → Gemini tool schema mapping ----------

def _mcp_arg_to_gemini_param(arg: Dict[str, Any]) -> Dict[str, Any]:
    type_map = {
        "string": "STRING", "number": "NUMBER", "integer": "NUMBER",
        "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT",
    }

    def pick_type(schema: Dict[str, Any]) -> str:
        if "anyOf" in schema and isinstance(schema["anyOf"], list):
            candidates = [s for s in schema["anyOf"] if s.get("type") != "null"]
            precedence = ["number", "integer", "string", "boolean", "array", "object"]
            for pref in precedence:
                for s in candidates:
                    if s.get("type") == pref:
                        return type_map.get(pref, "STRING")
            return "STRING"
        return type_map.get(schema.get("type", "string"), "STRING")

    def map_items(items_schema: Dict[str, Any]) -> Dict[str, Any]:
        if "anyOf" in items_schema and isinstance(items_schema["anyOf"], list):
            precedence = ["number", "integer", "string", "boolean", "array", "object"]
            for pref in precedence:
                for s in items_schema["anyOf"]:
                    if s.get("type") == pref:
                        return {"type": pick_type(s)}
            return {"type": "STRING"}
        return {"type": pick_type(items_schema)}

    g: Dict[str, Any] = {"type": pick_type(arg)}
    if arg.get("description"):
        g["description"] = arg["description"]
    if isinstance(arg.get("enum"), list):
        g["enum"] = arg["enum"]

    base_for_items = arg
    if "anyOf" in arg and isinstance(arg["anyOf"], list):
        array_branch = next((s for s in arg["anyOf"] if s.get("type") == "array"), None)
        if array_branch is not None:
            base_for_items = array_branch
    if base_for_items.get("type") == "array" and isinstance(base_for_items.get("items"), dict):
        g["items"] = map_items(base_for_items["items"])

    # if "default" in arg and arg["default"] is not None:
    #     g["default"] = arg["default"]
    return g


def _mcp_tool_to_gemini_function(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert one MCP tool spec into a Gemini function_declaration."""
    # Be tolerant to dicts/objects coming from MCP client
    name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", "")
    desc = (tool.get("description") if isinstance(tool, dict) else getattr(tool, "description", "")) or ""
    schema = (tool.get("inputSchema") if isinstance(tool, dict) else getattr(tool, "inputSchema", {})) or {}
    props = schema.get("properties", {})
    required = schema.get("required", [])
    gemini_props: Dict[str, Any] = {pname: _mcp_arg_to_gemini_param(pdef) for pname, pdef in props.items()}
    return {
        "name": name,
        "description": desc,
        "parameters": {"type": "OBJECT", "properties": gemini_props, "required": required},
    }


# ---------- Orchestrator with embedding router ----------

SYSTEM_HTTP = (
    "You are an autonomous agent. Your goal is to answer the user's request using the provided tools. "
    "You must not ask for clarification or permission before calling a tool.\n"
    "If the user's query is vague (e.g., 'give me a blog post') but one or more API CARDS are relevant, "
    "you must autonomously select the *single best* API from the cards and call it to fulfill the request.\n\n"
    "You may call the HTTP tool `fetch_data` ONLY if the user needs external data.\n"
    "When you call it, use an endpoint that appears in the API CARDS below.\n"
    "Arguments: endpoint (https URL), params (object), headers (object), method (GET/POST/PUT/PATCH/DELETE/HEAD/OPTIONS; default GET unless body present), body (object|string).\n"
)

class GeminiMCPOrchestrator:
    def __init__(
        self,
        gemini_api_key_env: str = "GOOGLE_API_KEY",
        mcp_target: str = "http://localhost:8000/mcp",
        model_name: str = "gemini-2.0-flash",
        autoload_env: bool = True,
        pg_dsn_env: str = "PG_DSN",
        api_threshold: float = 0.70,
        top_k: int = 5,
    ) -> None:
        if autoload_env:
            try:
                # Get the directory of the current script
                script_dir = Path(__file__).resolve().parent
                # Go up two levels to find .env.local
                env_path = script_dir.parent / ".env.local"
            except NameError:
                # Fallback for interactive shells (e.g., REPL, Jupyter)
                print("Warning: __file__ not defined. Using current working directory.")
                env_path = Path.cwd().parent / ".env.local"

            print(f"Loading .env file from: {env_path}")
            success = load_dotenv(dotenv_path=env_path)
            
            if not success:
                print(f"Warning: Could not find .env.local file at {env_path}")

        api_key = os.environ.get(gemini_api_key_env)
        if not api_key:
            raise ValueError(f"{gemini_api_key_env} not set. Check your .env file.")
        genai.configure(api_key=api_key)

        self.model_name = model_name
        self.mcp_target = mcp_target
        self.pg_dsn = os.environ.get(pg_dsn_env, "postgresql://postgres:password@localhost:5432/postgres")
        self.api_threshold = api_threshold
        self.top_k = top_k
        self.model = None  # built lazily after we fetch tools from MCP

    async def _discover_tools_from_mcp(self) -> Tool:
        async with MCPClient(self.mcp_target) as mcp:
            mcp_tools = await mcp.list_tools()
            decls = [FunctionDeclaration(**_mcp_tool_to_gemini_function(t)) for t in mcp_tools]
            return Tool(function_declarations=decls)

    async def _ensure_model(self):
        if self.model is None:
            tool_block = await self._discover_tools_from_mcp()
            self.model = genai.GenerativeModel(
                model_name=self.model_name,
                tools=[tool_block],
                system_instruction="You are a helpful assistant. Use tools only when external data is required."
            )
    def _deep_convert_map_composite(self, obj: Any) -> Any:
        """
        Recursively converts "dict-like" objects (like MapComposite)
        and their contents into plain Python dicts and lists.
        """
        # This check is the fix:
        # Instead of isinstance(obj, dict), we check for the .items() method.
        # This works for both regular dicts and MapComposite.
        if hasattr(obj, 'items'):
            return {k: self._deep_convert_map_composite(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_convert_map_composite(v) for v in obj]
        else:
            return obj

    def _extract_function_calls(self, response) -> List[Dict[str, Any]]:
        out = []
        for cand in getattr(response, "candidates", []) or []:
            
            for part in cand.content.parts:
                print('PART')
                pprint.pprint(part)
                fc = getattr(part, "function_call", None)
                if fc:
                    # Use the deep-convert helper to create a plain dict
                    plain_args = self._deep_convert_map_composite(fc.args)
                    out.append({"name": fc.name, "args": plain_args})
        return out

    async def run_query(self, user_query: str) -> str:
        await self._ensure_model()

        # ---- Embedding router ----
        q_emb = embed_query(user_query)
        candidates = retrieve_api_candidates(self.pg_dsn, q_emb, k=self.top_k)
        top_sim = candidates[0]["cosine_sim"] if candidates else 0.0
        # If below threshold → no tool; answer directly
        if not candidates or (top_sim is None) or (top_sim < self.api_threshold):
            plan = self.model.generate_content(contents=[
                {"role": "user", "parts": [{"text": user_query}]}
            ])
            return plan.text
        
        # Above threshold → include API CARDS and let model plan a function_call
        api_cards = make_api_cards(candidates)
        # print('API_CARDS')
        # pprint.pprint(api_cards)
        
        plan = self.model.generate_content(
            contents=[
                {"role": "model", "parts": [{"text": SYSTEM_HTTP}]},
                {"role": "model", "parts": [{"text": f"API CARDS (use only these):\n{api_cards}"}]},
                {"role": "user",  "parts": [{"text": user_query}]},
            ]
        )
        # print('Plan')
        # pprint.pprint(plan)
        calls = self._extract_function_calls(plan)
        print(calls)
        if not calls:
            # Model decided to answer without tools
            return plan.text

        # Execute tool calls with allowlist validation
        async with MCPClient(self.mcp_target) as mcp:
            tool_parts = []
            for call in calls:
                name = call["name"]
                args = call["args"]
                if name != "fetch_data":
                    tool_parts.append({"function_response": {"name": name, "response": {"error": "unknown tool"}}})
                    continue

                endpoint = args.get("endpoint")
                method = args.get("method")
                params = args.get("params")
                headers = args.get("headers")
                body = args.get("body") # body is allowed to be None
                if not isinstance(endpoint, str) or not endpoint.startswith("https://") or not endpoint_allowed(endpoint, candidates):
                    tool_parts.append({"function_response": {"name": name, "response": {"error": f"Invalid or disallowed endpoint: {endpoint}"}}})
                    continue
                
                # 2. Check other arguments for correct type (this is the fix)
                if method is not None and not isinstance(method, str):
                    tool_parts.append({"function_response": {"name": name, "response": {"error": f"Invalid 'method', must be a string, got {type(method)}"}}})
                    continue
                
                if params is not None and not isinstance(params, dict):
                    tool_parts.append({"function_response": {"name": name, "response": {"error": f"Invalid 'params', must be an object/dict, got {type(params)}"}}})
                    continue

                if headers is not None and not isinstance(headers, dict):
                    tool_parts.append({"function_response": {"name": name, "response": {"error": f"Invalid 'headers', must be an object/dict, got {type(headers)}"}}})
                    continue
                
                if body is not None and not isinstance(body, (dict, str)):
                    tool_parts.append({"function_response": {"name": name, "response": {"error": f"Invalid 'body', must be an object/dict or string, got {type(body)}"}}})
                    continue

                # Normalize containers
                for k in ("params", "headers"):
                    if k in args and not isinstance(args[k], dict):
                        tool_parts.append({"function_response": {"name": name, "response": {"error": f"{k} must be object"}}})
                        break
                
                result = await mcp.call_tool("fetch_data", args)
                
                # Extract the dictionary from the result object
                response_data = result.structured_content
                if result.is_error:
                    # Ensure errors are also passed back as simple dictionaries
                    response_data = {"error": str(response_data) or "Tool call failed"}

                tool_parts.append({"function_response": {"name": "fetch_data", "response": response_data}})

        # Finalize
        final = self.model.generate_content(
            contents=[
                {"role": "user", "parts": [{"text": user_query}]},
                *[{"role": "model", "parts": [{"function_call": c}]} for c in calls],
                {"role": "tool",  "parts": tool_parts},
            ]
        )
        return final.text

    def run(self, user_query: str) -> str:
        return asyncio.run(self.run_query(user_query))


if __name__ == "__main__":
    orch = GeminiMCPOrchestrator(
        mcp_target="http://localhost:8000/mcp",
        model_name="gemini-2.0-flash",
        api_threshold=0.70,   # tweak as you observe behavior
        top_k=5,
    )
    print(orch.run("Give a fake blog post"))
    print(orch.run("Give me a random trivia fact, irrespective of the difficult or category"))
