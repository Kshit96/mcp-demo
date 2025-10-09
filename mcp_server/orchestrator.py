"""
orchestrator.py
---------------
Uses Gemini as the orchestrator
Uses the relevant tool based on the query using the MCP client
Return the answer with the added context

To execute: PYTHONPATH=. python3 -m mcp_server.orchestrator

"""

from typing import Any, Dict, List, Optional
from google import genai
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai.types import (  # CORRECT: Import Tool and FunctionDeclaration
    FunctionDeclaration,
    Tool,
)
import os
import json
import asyncio

from mcp_server.client import MCPClient


def _mcp_arg_to_gemini_param(arg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a single MCP tool argument schema into Gemini's parameter format.
    This is a minimal mapper for common types; extend as needed.
    MCP typically returns JSON-schema-like fields (type, description, enum, etc.).
    Gemini expects:
      {
        "type": "OBJECT",
        "properties": { ... },
        "required": [ ... ]
      }
    We'll return a property entry (to be nested under 'properties').
    """
    g: Dict[str, Any] = {}
    t = arg.get("type", "string")
    # Map basic JSON types to Gemini types
    # Gemini expects uppercase names: STRING, NUMBER, BOOLEAN, ARRAY, OBJECT
    type_map = {
        "string": "STRING",
        "number": "NUMBER",
        "integer": "NUMBER",
        "boolean": "BOOLEAN",
        "array": "ARRAY",
        "object": "OBJECT",
    }
    g["type"] = type_map.get(t, "STRING")
    if "description" in arg and arg["description"]:
        g["description"] = arg["description"]
    # Optional enum mapping
    if "enum" in arg and isinstance(arg["enum"], list):
        g["enum"] = arg["enum"]
    # Optional items mapping for arrays
    if t == "array" and isinstance(arg.get("items"), dict):
        g["items"] = {"type": type_map.get(arg["items"].get("type", "string"), "STRING")}
    return g

def _mcp_tool_to_gemini_function(tool: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert one MCP tool spec into a Gemini function_declaration.
    Expected MCP shape (simplified):
      {
        "name": "fetch_data",
        "description": "…",
        "inputSchema": {
          "type": "object",
          "properties": { "endpoint": {...}, ... },
          "required": ["endpoint"]
        }
      }
    Returns:
      {
        "name": "fetch_data",
        "description": "...",
        "parameters": {
          "type": "OBJECT",
          "properties": { "endpoint": { "type": "STRING", ... } },
          "required": ["endpoint"]
        }
      }
    """
    name = tool.name
    desc = tool.description or ""
    schema = tool.inputSchema or {}
    props = schema.get("properties", {})
    required = schema.get("required", [])

    gemini_props: Dict[str, Any] = {}
    for pname, pdef in props.items():
        gemini_props[pname] = _mcp_arg_to_gemini_param(pdef)

    return {
        "name": name,
        "description": desc,
        "parameters": {
            "type": "OBJECT",
            "properties": gemini_props,
            "required": required,
        },
    }

class GeminiMCPOrchestrator:
    """
    Orchestrates tool use:
      1) Send user query to Gemini with tool declarations
      2) If Gemini emits a function_call, execute via MCP
      3) Feed tool results back to Gemini for the final answer
    """

    def __init__(
            self,
            gemini_api_key_env: str = "GOOGLE_API_KEY",
            mcp_target: str = "http://localhost:8000/mcp",
            model_name: str = "gemini-2.0-flash",
            system_instructions: Optional[str] = None,
            autoload_env: bool = True,
    ) -> None:
        """
        Args:
          gemini_api_key_env: env var name holding the Gemini API key.
          mcp_target: import path to your MCP app (module:object).
          pythonpath: added to Python path for the MCP client.
          model_name: Gemini model id.
          system_instructions: optional system guidance for the model.
          tools: optional custom tool declarations (defaults to fetch_data).
          autoload_env: load .env/.env.local automatically.
        """
        if autoload_env:
            load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.local"))
        
        api_key = os.environ.get(gemini_api_key_env)

        genai.configure(api_key=api_key)

        if not api_key:
            raise ValueError(f"{gemini_api_key_env} not set")

        self.model_name = model_name
        self.system_instructions = system_instructions or (
            "You are a helpful assistant. Use tools when they provide relevant data. "
            "Only call functions with strictly valid arguments that match their schema."
        )
        self.mcp_target = mcp_target
        # Built at runtime after we fetch tools from MCP:
        self.model = None
    
    async def _discover_tools_from_mcp(self) -> List[Dict[str, Any]]:
        """
        Ask the MCP server for its tools and convert them into Gemini function declarations.
        """

        async with MCPClient(self.mcp_target) as mcp:
            mcp_tools = await mcp.list_tools()

            functions_as_dicts = [_mcp_tool_to_gemini_function(t) for t in mcp_tools]
            declarations = [FunctionDeclaration(**d) for d in functions_as_dicts]
            gemini_tool = Tool(function_declarations=declarations)

            return gemini_tool, mcp_tools
    
    def _extract_function_calls(self, response) -> List[Any]:
        calls = []
        for cand in getattr(response, "candidates", []) or []:
            for part in cand.content.parts:
                if getattr(part, "function_call", None):
                    calls.append(part.function_call)
        return calls
    
    async def _ensure_model(self):
          # Build model lazily after we’ve fetched tool declarations from MCP
          if self.model is None:
              tool_blocks, _ = await self._discover_tools_from_mcp()
              self.model = genai.GenerativeModel(
                  model_name=self.model_name,
                  tools=[tool_blocks],
                  system_instruction=self.system_instructions
              )
    
    async def _execute_tool_calls(self, calls, mcp: MCPClient) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for call in calls:
            name = getattr(call, "name", None)
            args = dict(getattr(call, "args", {}) or {})
            try:
                # Dispatch dynamically to whatever tool Gemini chose:
                mcp_result = await mcp.call_tool(name, args)
                results.append(
                    {"function_response": {"name": name, "response": dict(mcp_result.content[0])}}
                )
            except Exception as e:
                results.append(
                    {"function_response": {"name": name or "unknown", "response": {"error": str(e)}}}
                )
        return results
    
    async def run_query(self, user_query: str) -> str:

        await self._ensure_model()

        plan = self.model.generate_content(
            contents=[
                {"role": "user", "parts":[{"text": user_query}]}],
        )

        calls = self._extract_function_calls(plan)

        if not calls:
            return plan.text
        
        async with MCPClient(self.mcp_target) as mcp:
            tool_parts = await self._execute_tool_calls(calls, mcp)
        
        final = self.model.generate_content(
            contents=[
                {"role": "user", "parts": [{"text": user_query}]},
                plan.candidates[0].content,
                {"role": "tool", "parts": tool_parts},
            ]
        )

        return final.text
    
    def run(self, user_query: str) -> str:
        return asyncio.run(self.run_query(user_query))

if __name__ == "__main__":
    orch = GeminiMCPOrchestrator(
        mcp_target="http://localhost:8000/mcp",
        model_name="gemini-2.0-flash",
    )
    print(orch.run("Get the repo name and stars for /repos/openai/openai-python"))