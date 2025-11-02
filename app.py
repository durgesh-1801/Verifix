# app.py
# Corrected, demo-safe backend for Invoice <-> PO verification
from flask import Flask, request, render_template, jsonify, redirect, url_for, session
from flask_cors import CORS
import os
import json
import base64
import mimetypes
import email
import pickle
from io import BytesIO
import requests

# Google Gmail API pieces (kept from your original)
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ---------------------------
# Configuration / Environment
# ---------------------------
# You can set these in environment or keep empty to use mock fallback.
# ---------------------------
# Configuration / Environment
# ---------------------------

# ⚙️ Directly set your Shivaay LLM API credentials here for demo use.
# (No need to run setx/export commands)

FUTURIXAI_API_KEY = "6903664e3bb9326d46566470"   # <-- your API key
FUTURIXAI_API_BASE = "https://api.futurixai.com/api/shivaay/v1"  # <-- your API endpoint

print("✅ Using hardcoded API key and base URL for Shivaay API.")

print("DEBUG: FUTURIXAI_API_KEY present:", bool(FUTURIXAI_API_KEY))
print("DEBUG: FUTURIXAI_API_BASE:", FUTURIXAI_API_BASE)

# Allow OAuth on localhost for Gmail flow
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

# Gmail/OAuth config (unchanged)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CLIENT_SECRETS_FILE = 'client_secret.json'
CREDENTIALS_FILE = 'token.pickle'


# ---------------------------
# Helper: Mock fallback
# ---------------------------
def mock_ai_response_from_filename(filename):
    """
    Simple demo fallback response when real API is not available.
    Returns structured fields similar to what LLM should produce.
    """
    name = (filename or "").lower()
    if "po" in name:
        return {
            "document_type": "Purchase Order",
            "vendor_name": "TechWorld Pvt Ltd",
            "total_amount": "24000",
            "line_items": [
                {"description": "Mouse (Model MX-200)", "quantity": "10", "unit_price": "500"},
                {"description": "Keyboard (Model KB-500)", "quantity": "5", "unit_price": "1000"},
                {"description": "Monitor (24-inch LED)", "quantity": "2", "unit_price": "7000"}
            ]
        }
    else:
        # invoice fallback
        return {
            "document_type": "Invoice",
            "vendor_name": "TechWorld Pvt Ltd",
            "total_amount": "28500",
            "line_items": [
                {"description": "Mouse (Model MX-200)", "quantity": "10", "unit_price": "500"},
                {"description": "Keyboard (Model KB-500)", "quantity": "5", "unit_price": "1200"},
                {"description": "Monitor (24-inch LED)", "quantity": "3", "unit_price": "7000"}
            ]
        }

# ---------------------------
# Helper: Call Shivaay API (via requests)
# ---------------------------
def call_shivaay_for_text(po_text: str, invoice_text: str):
    """
    Calls the Shivaay endpoint to compare two texts and return structured JSON.
    If API fails or key is missing, returns None so caller uses fallback.
    """
    if not FUTURIXAI_API_KEY:
        print("DEBUG: No API key configured, skipping real API call.")
        return None

    prompt = (
        "You are a strict document verification AI. Compare the Purchase Order (PO) and the Invoice below. "
        "Return a JSON object with fields: status (either 'Matched' or 'Discrepancies Found'), "
        "discrepancies (list of human-readable items), po_data (structured), invoice_data (structured). "
        "Be precise: check vendor_name, each line item description, quantity, unit_price, payment terms, and total amount. "
        "If there are NO differences, set status to 'Matched' and discrepancies: [].\n\n"
        "Purchase Order:\n" + po_text + "\n\nInvoice:\n" + invoice_text
    )

    payload = {
        "model": "shivaay",
        "input": [
            {"role": "user", "content": prompt}
        ]
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-key": FUTURIXAI_API_KEY
    }

    try:
        url = FUTURIXAI_API_BASE.rstrip("/") + "/verify"
        print("DEBUG: calling Shivaay at", url)
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        print("DEBUG: Shivaay status_code:", r.status_code)
        if r.status_code == 200:
            # Expect JSON response already structured
            return r.json()
        else:
            print("WARN: Shivaay returned non-200:", r.text)
            return None
    except Exception as e:
        print("ERROR calling Shivaay:", e)
        return None


# ---------------------------
# Helper: Extract data using AI or fallback
# ---------------------------
def extract_data_from_uploaded_file(file_storage):
    """
    Reads the uploaded file. For simplicity we try to decode text files.
    If not text (binary), we send placeholder text describing the filename.
    Then call Shivaay to parse fields; if that fails, return mock data based on filename.
    """
    filename = getattr(file_storage, "filename", "unknown")
    try:
        file_storage.seek(0)
        raw = file_storage.read()
        # try decode as utf-8 text
        try:
            text = raw.decode("utf-8")
        except Exception:
            # binary (pdf/image) -> we can't OCR here (no extra deps); use filename marker
            text = f"[binary file: {filename}]"
    except Exception as e:
        print("ERROR reading uploaded file:", e)
        text = f"[could not read file: {filename}]"

    # We don't call per-file extraction here; higher-level compare function does pairwise call.
    # But for completeness, return minimal structure in case we need it.
    return {"raw_text": text, "filename": filename}


# ---------------------------
# Comparison Logic (existing)
# ---------------------------
def verify_documents(po_data, invoice_data):
    discrepancies = []

    # normalize simple strings for comparison
    def norm(s):
        if s is None:
            return ""
        return str(s).strip().lower()

    if norm(po_data.get("vendor_name")) != norm(invoice_data.get("vendor_name")):
        discrepancies.append({
            "field": "Vendor Name",
            "po_value": po_data.get("vendor_name"),
            "invoice_value": invoice_data.get("vendor_name")
        })

    if norm(po_data.get("total_amount")) != norm(invoice_data.get("total_amount")):
        discrepancies.append({
            "field": "Total Amount",
            "po_value": po_data.get("total_amount"),
            "invoice_value": invoice_data.get("total_amount")
        })

    # map items by normalized description
    po_items = { (i.get("description") or "").strip().lower(): i for i in po_data.get("line_items", []) }
    inv_items = { (i.get("description") or "").strip().lower(): i for i in invoice_data.get("line_items", []) }

    for desc, po_item in po_items.items():
        if desc not in inv_items:
            discrepancies.append({"field": "Missing Item", "description": po_item.get("description"), "details": "Item on PO but not on invoice."})
        else:
            inv_item = inv_items[desc]
            if str(po_item.get("quantity")) != str(inv_item.get("quantity")):
                discrepancies.append({
                    "field": "Item Quantity Mismatch",
                    "description": po_item.get("description"),
                    "po_value": po_item.get("quantity"),
                    "invoice_value": inv_item.get("quantity")
                })
            if str(po_item.get("unit_price")) != str(inv_item.get("unit_price")):
                discrepancies.append({
                    "field": "Item Price Mismatch",
                    "description": po_item.get("description"),
                    "po_value": po_item.get("unit_price"),
                    "invoice_value": inv_item.get("unit_price")
                })

    status = "Matched" if not discrepancies else "Discrepancies Found"
    return {"status": status, "discrepancies": discrepancies, "po_data": po_data, "invoice_data": invoice_data}


# ---------------------------
# Routes: Home + Upload page
# ---------------------------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/upload")
def upload_page():
    # initial visit: show no result
    return render_template("upload.html", result_json={}, status="Pending")


# ---------------------------
# Single /verify route (manual upload)
# ---------------------------
@app.route("/verify", methods=["POST"])
def verify_route():
    invoice_file = request.files.get("invoiceFile")
    po_file = request.files.get("poFile")

    if not invoice_file or not po_file:
        return render_template("upload.html", result_json={}, status="Error")

    # read basic text/placeholder from files (so we can include text in prompt)
    inv = extract_data_from_uploaded_file(invoice_file)
    po = extract_data_from_uploaded_file(po_file)

    invoice_text = inv["raw_text"]
    po_text = po["raw_text"]

    # Try calling Shivaay compare endpoint for a structured comparison
    ai_result = call_shivaay_for_text(po_text=po_text, invoice_text=invoice_text)

    if ai_result:
        # If Shivaay returned structured result, use it (assume it contains po_data, invoice_data and discrepancies)
        # Normalize status key if necessary
        status = ai_result.get("status") or ai_result.get("result_status") or ("Matched" if not ai_result.get("discrepancies") else "Discrepancies Found")
        report = {
            "status": status,
            "discrepancies": ai_result.get("discrepancies", []),
            "po_data": ai_result.get("po_data", ai_result.get("po", {})),
            "invoice_data": ai_result.get("invoice_data", ai_result.get("invoice", {}))
        }
    else:
        # API not available or failed — use local parsing fallback:
        print("DEBUG: Using local fallback parsing + mock data.")
        # get structured mocks from filenames (these intentionally produce discrepancies for your demo PO/invoice)
        po_struct = mock_ai_response_from_filename(po["filename"])
        invoice_struct = mock_ai_response_from_filename(inv["filename"])
        # If both filenames indicate real demo PO/invoice pair, keep them as is (mock has differences)
        report = verify_documents(po_struct, invoice_struct)

    # Render the polished upload.html with result (no raw JSON displayed by default)
    return render_template("upload.html", result_json=report, status=report.get("status", "Error"))


# ---------------------------
# (Optional) Gmail flow kept mostly intact; simplified return for demo
# ---------------------------
@app.route('/check_gmail')
def check_gmail():
    credentials = None
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'rb') as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=url_for('oauth2callback', _external=True))
            authorization_url, state = flow.authorization_url(access_type='offline', include_granted_scopes='true')
            session['oauth_state'] = state
            return redirect(authorization_url)

    # For demo keep this simple: process last few emails (existing code possible to plug in)
    # If you want full Gmail processing, re-use your earlier process_gmail_attachments implementation.
    return jsonify({"status": "Gmail scan not fully enabled in this demo build."})


@app.route('/oauth2callback')
def oauth2callback():
    state = session.get('oauth_state')
    flow = Flow.from_client_secrets_file(CLIENT_SECRETS_FILE, scopes=SCOPES, state=state, redirect_uri=url_for('oauth2callback', _external=True))
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    with open(CREDENTIALS_FILE, 'wb') as token:
        pickle.dump(credentials, token)
    return redirect(url_for('check_gmail'))


# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
