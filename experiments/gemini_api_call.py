from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env.local"))

client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Tell me a joke",
    config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0) # Disables thinking
    ),
)

print(response.text)