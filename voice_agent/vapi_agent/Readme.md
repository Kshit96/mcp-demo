# Vanessa - AI Real Estate Acquisitions Agent

This project is a prototype of "Vanessa," a voice AI agent designed to make automated outbound calls to property owners to qualify their interest in selling.

The system is built using Python, the Vapi voice AI platform, and a Flask web server for handling results.

## Features

* **Automated Outbound Dialing**: Reads a list of contacts from a CSV file and places calls sequentially.
* **Personalized Conversations**: Dynamically inserts the property address into the agent's opening line.
* **Intelligent Conversation**: Uses a Gemini-powered agent on the Vapi platform to have natural conversations and detect seller intent.
* **Structured Data Extraction**: After each call, Vapi analyzes the conversation and extracts key details:
  * `openness`: Is the owner interested, unsure, or not interested?
  * `timing`: What is their potential selling timeline?
  * `price`: What is their desired price range?
  * `notes`: Any other important context from the call.
* **Live Dashboard**: A simple, auto-refreshing web page displays the results of each call as they come in.

## How It Works

The system is composed of two main Python scripts that run in parallel:

1. **`phone.py` (The Dialer):**
   * Reads contact information from `leads.csv`.
   * Loops through each contact and tells the Vapi API to start a call.
   * Personalizes the agent's first message for each call.

2. **`webhook_server.py` (The Results Handler):**
   * Runs a local Flask web server.
   * A tunneling service like **ngrok** exposes this local server to the internet with a public URL.
   * Vapi is configured to send a detailed `end-of-call-report` to this public URL after each call.
   * The server receives the report, extracts the structured data, and appends it to `dashboard.csv`.
   * It also hosts a simple webpage at `http://localhost:8001` that displays the contents of `dashboard.csv`.

## Setup and Installation

1. **Clone the Repository**
   * Ensure all project files are in the same directory.

2. **Install Dependencies**
   * It is highly recommended to use a Python virtual environment.
   * Install the required packages from `requirements-vapi.txt`:
     ```bash
     pip install -r requirements-vapi.txt
     ```
   * You will also need **Flask** for the webhook server and **Gunicorn** to run it robustly (optional but recommended):
     ```bash
     pip install Flask gunicorn
     ```

3. **Configure Environment Variables**
   * Rename the `.env.example` file to `.env`.
   * Open the `.env` file and fill in your Vapi credentials:
     ```env
     VAPI_API_KEY="your-secret-api-key-from-vapi"
     VAPI_ASSISTANT_ID="your-vanessa-assistant-id-from-vapi"
     VAPI_PHONE_NUMBER_ID="your-verified-phone-number-id-from-vapi"
     ```

4. **Prepare Leads**
   * Open `leads.csv` and add the contact information for the property owners you want to call. Ensure the `phone_number` is in E.164 format (e.g., `+15551234567`).

4. **Setting up Vapi Agent**
   * The VAPI agent is setup on the VAPI dashboard with the system prompts, structured data configurations, end call configurations and the webhook server url
   * The full config of how I set it up can be found in the file `vanessa_config.json`

## Usage

You will need to run two processes in separate terminal windows.

**Terminal 1: Start the Webhook Server & Tunnel**

1. **Start the Server:**
   * Run the Flask server. For production use, it's best to use Gunicorn.
     ```bash
     gunicorn --workers 4 --bind 0.0.0.0:8001 webhook_server:app
     ```
   * (For simple testing, you can use: `python3 webhook_server.py`)

2. **Start a Tunnel:**
   * In a new terminal window, use `ngrok` to expose your local server.
     ```bash
     # Using ngrok
     ngrok http 8001 --host-header="localhost:8001"
     ```
   * Copy the public `https://` URL provided by ngrok.

3. **Configure Vapi Dashboard:**
   * Go to your "Vanessa" assistant settings in the Vapi dashboard.
   * In the **Server URL** field, paste your ngrok URL and append the webhook path:
     `https://<your-ngrok-id>.ngrok-free.app/webhook/vapi`
   * Ensure the **Server Message Types** is set to only send the `end-of-call-report`.
   * Save your assistant.

**Terminal 2: Start Making Calls**

1. **Run the Dialer Script:**
   * Once the webhook is ready, run the `phone.py` script to start dialing the numbers from `leads.csv`.
     ```bash
     python3 phone.py
     ```

## Checking the Output

1. **Live Dashboard (Primary Output):**
   * Open your web browser and navigate to **`http://localhost:8001`**.
   * This page will auto-refresh every 10 seconds, showing the latest call results from `dashboard.csv` at the top.

2. **Structured Data File (`dashboard.csv`):**
   * This CSV file is the source of truth for the dashboard. It contains one row for each completed call with the extracted `openness`, `timing`, `price`, and `notes`.

3. **Raw Debug Log (`webhook_log.json`):**
   * This file contains the complete, raw JSON payload sent by Vapi for every webhook request. It is very useful for debugging if the data is not being extracted correctly.