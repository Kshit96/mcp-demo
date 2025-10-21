from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search

# Mock tool implementation
def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city."""
    return {"status": "success", "city": city, "time": "10:30 AM"}

root_agent = Agent(
   # A unique name for the agent.
   name="basic_search_agent",
   # The Large Language Model (LLM) that agent will use.
   # Please fill in the latest model id that supports live from
   # https://google.github.io/adk-docs/get-started/streaming/quickstart-streaming/#supported-models
   model="gemini-2.0-flash-live-001",  # for example: model="gemini-2.0-flash-live-001" or model="gemini-2.0-flash-live-preview-04-09"
   # A short description of the agent's purpose.
   description="Agent to answer questions using Google Search.",
   # Instructions to set the agent's behavior.
   instruction="You are an expert researcher. You always stick to the facts. The tone of your voice should be warm, upbeat, and confident, with light assertiveness -- never robotic or pushy",
   # Add google_search tool to perform grounding with Google search.
   tools=[google_search]
)

# To Run with mic locally, you need an https Connection
# The default 'adk web  --port 8080' will run in http
# So we can use a reverse proxy tool like caddy to run this with mic
# Run Agent: adk web  --port 8080
# Install caddy: brew install caddy (for mac)
# Run Caddy: caddy reverse-proxy --from localhost --to localhost:8080
