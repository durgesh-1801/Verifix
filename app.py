# app.py
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import json
import os
import base64
from openai import OpenAI
import mimetypes # For handling file types from attachments
import email # For parsing email content

# --- Google API Imports ---
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import pickle # To store user credentials securely

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
# --- Setup Flask App ---
app = Flask(__name__)
app.secret_key = os.urandom(24) # A secret key is required for Flask sessions
CORS(app)

# --- Configuration for Gmail API ---
# The SCOPES define what your app can do with the user's Gmail.
# For reading attachments, 'readonly' is usually sufficient.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
# This file needs to be downloaded from Google Cloud Console
CLIENT_SECRETS_FILE = 'client_secret.json'
# Where user credentials will be stored after first authentication
CREDENTIALS_FILE = 'token.pickle' # Stores the OAuth tokens

# --- Routes for Frontend HTML ---
@app.route('/')
def index():
    return render_template('home.html')
@app.route('/upload')
def upload_page():
    return render_template('upload.html')
# --- NEW: Route to trigger Gmail checking ---
@app.route('/check_gmail')
def check_gmail():
    # This route initiates the OAuth 2.0 flow if credentials are not found
    credentials = None
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, 'rb') as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES,
                redirect_uri=url_for('oauth2callback', _external=True) # Important for local dev
            )
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            session['oauth_state'] = state
            return redirect(authorization_url) # Redirect user to Google for login
    
    # If credentials are valid, proceed to fetch emails
    return process_gmail_attachments(credentials)


# --- NEW: Callback route after user grants permission to Google ---
@app.route('/oauth2callback')
def oauth2callback():
    state = session['oauth_state']
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    
    # Exchange the authorization code for credentials
    authorization_response = request.url
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    with open(CREDENTIALS_FILE, 'wb') as token:
        pickle.dump(credentials, token)

    return redirect(url_for('check_gmail')) # Redirect back to process emails


# --- NEW: Function to process attachments ---
def process_gmail_attachments(credentials):
    try:
        service = build('gmail', 'v1', credentials=credentials)
        results = service.users().messages().list(userId='me', q="has:attachment -in:chats").execute()
        messages = results.get('messages', [])

        if not messages:
            return jsonify({"status": "No new messages with attachments found."})

        verified_reports = []

        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
            
            # --- Extract files from attachments ---
            # This logic needs to be robust for various email formats.
            # Simplified for demo: assuming attachments are direct files, not inline.
            email_payload = email.message_from_string(base64.urlsafe_b64decode(msg['raw']).decode('utf-8'))
            
            for part in email_payload.walk():
                if part.get_filename():
                    filename = part.get_filename()
                    if part.get('Content-Disposition', '').startswith('attachment'):
                        # Attachments are base64 encoded
                        file_data = part.get_payload(decode=True)
                        
                        # --- Create a mock file object for your AI function ---
                        # Your AI function expects a file-like object from Flask's request.files
                        # We simulate that here.
                        from io import BytesIO
                        mock_file = BytesIO(file_data)
                        mock_file.filename = filename
                        mock_file.mimetype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

                        # Store files temporarily or process directly
                        # For simplicity, we'll try to determine if it's a PO or Invoice based on filename
                        if "po" in filename.lower() and mock_file.mimetype in ['application/pdf', 'text/plain', 'image/jpeg', 'image/png']:
                            po_file_from_email = mock_file
                        elif "invoice" in filename.lower() and mock_file.mimetype in ['application/pdf', 'text/plain', 'image/jpeg', 'image/png']:
                            invoice_file_from_email = mock_file
            
            # --- If both PO and Invoice were found in THIS email, process them ---
            if 'po_file_from_email' in locals() and 'invoice_file_from_email' in locals():
                po_data = extract_data_with_ai(po_file_from_email)
                invoice_data = extract_data_with_ai(invoice_file_from_email)

                if "error" in po_data or "error" in invoice_data:
                    verified_reports.append({
                        "email_id": message['id'],
                        "status": "AI processing failed for this email's documents.",
                        "details": {"po_ai_error": po_data.get("error"), "invoice_ai_error": invoice_data.get("error")}
                    })
                else:
                    report = verify_documents(po_data, invoice_data)
                    report['email_id'] = message['id']
                    verified_reports.append(report)
            else:
                verified_reports.append({
                    "email_id": message['id'],
                    "status": "Could not identify both PO and Invoice attachments in this email, or unsupported file type."
                })
        
        return jsonify(verified_reports)

    except Exception as e:
        print(f"Error processing Gmail: {e}")
        return jsonify({"error": f"Failed to process Gmail: {str(e)}"})


# --- 1. REAL AI FUNCTION (SPONSOR TECH) ---
# (This function is unchanged from the previous version)
def extract_data_with_ai(file):
    """
    Calls the *real* FuturixAI LLM to extract data from a file.
    """
    print(f"AI: Processing file: {file.filename} with FuturixAI...")
    
    api_key = os.environ.get("FUTURIXAI_API_KEY")
    api_base_url = os.environ.get("FUTURIXAI_API_BASE")

    if not api_key:
        print("ERROR: FUTURIXAI_API_KEY environment variable not set.")
        return {"error": "API key is missing."}
    if not api_base_url:
        print("ERROR: FUTURIXAI_API_BASE environment variable not set.")
        return {"error": "API base URL is missing."}

    client = OpenAI(
        api_key=api_key,
        base_url=api_base_url,
    )

    try:
        file_content = file.read()
        base64_image = base64.b64encode(file_content).decode('utf-8')
        mime_type = file.mimetype 
        data_url = f"data:{mime_type};base64,{base64_image}"
    except Exception as e:
        print(f"Error encoding file: {e}")
        return {"error": "Failed to read or encode file."}

    prompt_messages = [
        {
            "role": "system",
            "content": "You are an expert financial analyst AI. You will be given an image or document of an invoice or purchase order. Extract the specified fields and return *only* a valid JSON object."
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """
                    Extract the following fields from this document:
                    - document_type (string, e.g., "Invoice" or "Purchase Order")
                    - vendor_name (string)
                    - total_amount (string)
                    - line_items (a list of objects, where each object has "description", "quantity", and "unit_price")

                    Return only the raw JSON object.
                    """
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_url
                    }
                }
            ]
        }
    ]

    try:
        model_name = "shivaay-llm" # <-- This is a placeholder! Check sponsor docs.

        completion = client.chat.completions.create(
            model=model_name,
            messages=prompt_messages,
            max_tokens=1024,
            response_format={"type": "json_object"}
        )
        
        response_content = completion.choices[0].message.content
        json_data = json.loads(response_content)
        
        return json_data

    except Exception as e:
        print(f"Error calling AI API: {e}")
        return {"error": "AI API call failed.", "details": str(e)}

# --- 2. BUSINESS LOGIC (YOUR BACKEND CODE) ---
# (This function is unchanged from the previous version)
def verify_documents(po_data, invoice_data):
    """
    Compares the JSON data from the PO and the Invoice.
    This is the core business logic of your application.
    """
    discrepancies = []
    
    # Check 1: Vendor Name
    if po_data.get("vendor_name") != invoice_data.get("vendor_name"):
        discrepancies.append({
            "field": "Vendor Name",
            "po_value": po_data.get("vendor_name"),
            "invoice_value": invoice_data.get("vendor_name")
        })
        
    # Check 2: Total Amount
    if po_data.get("total_amount") != invoice_data.get("total_amount"):
        discrepancies.append({
            "field": "Total Amount",
            "po_value": po_data.get("total_amount"),
            "invoice_value": invoice_data.get("total_amount")
        })
        
    # Check 3: Line Items (a more complex check)
    po_items = {item['description']: item for item in po_data.get('line_items', [])}
    invoice_items = {item['description']: item for item in invoice_data.get('line_items', [])}
    
    for desc, po_item in po_items.items():
        if desc not in invoice_items:
            discrepancies.append({"field": f"Missing Item", "description": desc, "details": "Item on PO but not on Invoice."})
        else:
            invoice_item = invoice_items[desc]
            # Check quantity
            if po_item.get("quantity") != invoice_item.get("quantity"):
                discrepancies.append({
                    "field": "Item Quantity",
                    "description": desc,
                    "po_value": po_item.get("quantity"),
                    "invoice_value": invoice_item.get("quantity")
                })

    # Final Report
    report = {
        "status": "Flagged" if discrepancies else "Matched",
        "discrepancies": discrepancies,
        "po_data": po_data,
        "invoice_data": invoice_data
    }
    
    return report

# --- 3. FLASK API ENDPOINT (Unchanged) ---
@app.route('/verify', methods=['POST'])
def verify_endpoint():
    if 'invoiceFile' not in request.files or 'poFile' not in request.files:
        return jsonify({"error": "Missing one or both files."}), 400
        
    invoice_file = request.files['invoiceFile']
    po_file = request.files['poFile']

    invoice_data = extract_data_with_ai(invoice_file)
    po_data = extract_data_with_ai(po_file)
    
    if "error" in invoice_data or "error" in po_data:
        return jsonify({"error": "AI could not parse documents.", "details": [invoice_data, po_data]}), 500

    verification_report = verify_documents(invoice_data, po_data)
    
    return jsonify(verification_report)

# --- Run the App ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
