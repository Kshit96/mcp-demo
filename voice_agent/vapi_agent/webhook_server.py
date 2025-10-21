# webhook_server.py
from flask import Flask, request, jsonify, render_template
import pprint
import json
import csv
import os
from datetime import datetime

app = Flask(__name__)

LOG_FILE = "webhook_log.json"
DASHBOARD_CSV_FILE = "dashboard.csv"

# Define the headers for our dashboard CSV
CSV_HEADERS = [
    "timestamp", "call_id", "summary", 
    "openness", "timing", "price", "notes"
]

def initialize_dashboard_csv():
    """Create the dashboard CSV with headers if it doesn't exist."""
    if not os.path.exists(DASHBOARD_CSV_FILE):
        with open(DASHBOARD_CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)

def append_to_dashboard(report_data):
    """Appends a new row to the dashboard CSV file."""
    with open(DASHBOARD_CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow(report_data)

@app.route('/webhook/vapi', methods=['POST'])
def handle_vapi_webhook():
    """
    Receives the end-of-call-report, logs it, and writes structured data to a CSV.
    """
    data = request.json
    
    # Log the full raw request to a file for debugging
    try:
        with open(LOG_FILE, "a") as f:
            log_entry = {"timestamp": datetime.now().isoformat(), "payload": data}
            f.write(json.dumps(log_entry, indent=2) + "\n---\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

    # --- Data Extraction Logic ---
    message = data.get('message', {})
    
    if message and message.get('type') == 'end-of-call-report':
        report = message
        call_id = report.get('call', {}).get('id')
        analysis = report.get('analysis', {})
        intent_data = analysis.get('structuredData')
        
        if intent_data:
            print(f"✅ Received structured data for call ID: {call_id}")

            # Prepare the data for our dashboard
            dashboard_row = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "call_id": call_id,
                "summary": analysis.get('summary', 'N/A'),
                "openness": intent_data.get('openness', 'N/A'),
                "timing": intent_data.get('timing', 'N/A'),
                "price": intent_data.get('price', 'N/A'),
                "notes": intent_data.get('notes', 'N/A'),
            }
            
            # Append the new data to our CSV
            append_to_dashboard(dashboard_row)
        else:
            print(f"Call {call_id} ended, but no structured data was found.")
            
    return jsonify({"status": "ok"})

@app.route('/', methods=['GET'])
def dashboard():
    """
    Reads the dashboard CSV and renders it in an HTML template.
    """
    call_logs = []
    try:
        with open(DASHBOARD_CSV_FILE, mode='r', encoding='utf-8') as f:
            # Use DictReader to make data easy to use in the template
            reader = csv.DictReader(f)
            # Reverse the list so the newest calls appear at the top
            call_logs = sorted(list(reader), key=lambda x: x['timestamp'], reverse=True)
    except FileNotFoundError:
        print("dashboard.csv not found. It will be created on the first webhook call.")
    
    # Pass the log data to the HTML template
    return render_template('dashboard.html', logs=call_logs)

if __name__ == '__main__':
    initialize_dashboard_csv()
    print("🚀 Starting Flask server...")
    print("   - Webhook listening on http://localhost:8001/webhook/vapi")
    print("   - Dashboard available at http://localhost:8001/")
    app.run(port=8001, debug=True)

