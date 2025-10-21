import os
import json
from dotenv import load_dotenv
from vapi import Vapi

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
# Load the API Key and the ID of the assistant you want to export
VAPI_API_KEY = os.environ.get("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.environ.get("VAPI_ASSISTANT_ID")
OUTPUT_FILE_NAME = "vanessa_config.json"

# --- Main Script ---
def export_assistant_config():
    """
    Fetches the full configuration for a Vapi assistant and saves it to a JSON file.
    """
    if not all([VAPI_API_KEY, VAPI_ASSISTANT_ID]):
        print("🔴 Error: VAPI_API_KEY or VAPI_ASSISTANT_ID is missing from your .env file.")
        return

    print("🚀 Initializing Vapi client...")
    client = Vapi(token=VAPI_API_KEY)

    try:
        print(f"🔍 Fetching configuration for assistant ID: {VAPI_ASSISTANT_ID}...")
        
        # Use the Vapi client to get the assistant's details
        assistant_config = client.assistants.get(id=VAPI_ASSISTANT_ID)

        # The returned object is a Pydantic model; convert it to a dict for JSON serialization
        config_dict = assistant_config.model_dump(mode='json')

        # Save the configuration dictionary to a file
        with open(OUTPUT_FILE_NAME, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4)

        print(f"\n✅ Successfully exported assistant configuration to '{OUTPUT_FILE_NAME}'")

    except Exception as e:
        print(f"\n❌ An error occurred while fetching the assistant configuration: {e}")

if __name__ == "__main__":
    export_assistant_config()
