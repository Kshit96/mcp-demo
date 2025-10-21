import os
import pprint
import csv
import time
from dotenv import load_dotenv
from vapi import Vapi

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
LEADS_FILE_PATH = "leads.csv"

# Your Vapi API Key, Assistant ID, and Phone Number ID are loaded from your .env file
VAPI_API_KEY = os.environ.get("VAPI_API_KEY")
VAPI_ASSISTANT_ID = os.environ.get("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.environ.get("VAPI_PHONE_NUMBER_ID")

# --- Main Script ---
def process_leads():
    """Initializes the Vapi client, reads leads from a CSV, and places personalized calls."""
    
    # 1. Check if all required configuration values are loaded
    if not all([VAPI_API_KEY, VAPI_ASSISTANT_ID, VAPI_PHONE_NUMBER_ID]):
        print("🔴 Error: One or more required variables are missing.")
        print("Please ensure VAPI_API_KEY, VAPI_ASSISTANT_ID, and VAPI_PHONE_NUMBER_ID are set in your .env file.")
        return

    # 2. Read leads from the CSV file
    try:
        with open(LEADS_FILE_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            leads = list(reader)
    except FileNotFoundError:
        print(f"🔴 Error: The leads file was not found at '{LEADS_FILE_PATH}'.")
        return

    print(f"🚀 Found {len(leads)} leads to process. Initializing Vapi client...")
    client = Vapi(token=VAPI_API_KEY)

    # 3. Loop through each lead and make a personalized call
    for lead in leads:
        customer_number = lead.get("phone_number")
        property_address = lead.get("property_address")

        if not customer_number or not property_address:
            print(f"⚠️ Skipping lead ID '{lead.get('lead_id')}' due to missing phone number or address.")
            continue

        print("\n" + "-"*50)
        print(f"📞 Placing call to {customer_number} for property at '{property_address}'...")

        try:
            # Create the outbound call with a dynamically overridden first message
            call_result = client.calls.create(
                assistant_id=VAPI_ASSISTANT_ID,
                phone_number_id=VAPI_PHONE_NUMBER_ID,
                customer={
                    "number": customer_number
                },
                assistant_overrides={
                    "firstMessage": f"Hi, I'm calling for the owner of {property_address}? My name is Vanessa with Mozart Management. Is this a good time to talk?"
                }
            )

            print("✅ Call placed successfully!")
            print("Call Details:")
            pprint.pprint(call_result)

            # Add a delay between calls to avoid hitting rate limits
            print("Pausing for 5 seconds before next call...")
            time.sleep(5)

        except Exception as e:
            print(f"❌ An error occurred while calling {customer_number}: {e}")
    
    print("\n" + "-"*50)
    print("🎉 Finished processing all leads.")


if __name__ == "__main__":
    process_leads()