# app.py — Invoice / PO verification (Groq via llm.py, PDF text via ocr.py)
#
# Key fixes vs original:
#   - Logging configured at startup so DEBUG prints from ocr.py and llm.py are visible.
#   - File type validation: accepts .pdf and .txt. .txt files are decoded directly,
#     skipping the entire OCR pipeline (was a silent breakage before).
#   - pipeline_debug() logs every stage so you can pinpoint where data goes wrong.
#   - No logic change to Gmail / OAuth routes — left as-is.

from __future__ import annotations

import logging
import os
import pickle

from dotenv import load_dotenv

load_dotenv()

# ── Configure logging BEFORE any other import that uses the logger ──────────
logging.basicConfig(
    level=logging.DEBUG,          # flip to INFO in production
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_cors import CORS
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

from llm import compare_invoice_po
from ocr import extract_text_from_pdf


os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CLIENT_SECRETS_FILE = "client_secret.json"
CREDENTIALS_FILE = "token.pickle"

_ALLOWED_EXTENSIONS = {".pdf", ".txt"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Route file bytes to the correct extractor based on file extension.

    - .txt → decode directly (no OCR needed; was a silent failure before)
    - .pdf → pdfplumber + OCR fallback
    """
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".txt":
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            logger.debug("TXT '%s': decoded %d chars", filename, len(text))
            return text
        except Exception as exc:
            logger.error("TXT decode error for '%s': %s", filename, exc)
            return ""
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    logger.warning("Unsupported file type '%s' for '%s'", ext, filename)
    return ""


def _read_upload(field_name: str) -> tuple[bytes, str] | tuple[None, None]:
    """Read bytes + filename from a multipart field. Returns (None, None) on failure."""
    f = request.files.get(field_name)
    if not f or not getattr(f, "filename", None):
        return None, None
    ext = os.path.splitext(f.filename.lower())[1]
    if ext not in _ALLOWED_EXTENSIONS:
        logger.warning("Rejected file '%s' — unsupported extension '%s'", f.filename, ext)
        return None, None
    try:
        f.seek(0)
        data = f.read()
    except Exception as exc:
        logger.error("Could not read upload '%s': %s", field_name, exc)
        return None, None
    if not data:
        logger.warning("Upload '%s' is empty", field_name)
        return None, None
    return data, f.filename


def _run_pipeline(invoice_bytes: bytes, invoice_name: str,
                  po_bytes: bytes, po_name: str) -> dict:
    """
    Full pipeline: extract text → call LLM → return structured result.
    Logs every stage so you can see exactly where data breaks.
    """
    # Stage 1: text extraction
    invoice_text = _extract_text(invoice_bytes, invoice_name)
    po_text = _extract_text(po_bytes, po_name)

    logger.info(
        "PIPELINE STAGE 1 — Extraction: invoice=%d chars, po=%d chars",
        len(invoice_text), len(po_text),
    )
    # ── DEBUG: print first 300 chars of each so you can verify OCR quality ──
    logger.debug("INVOICE TEXT PREVIEW:\n%s", invoice_text[:300])
    logger.debug("PO TEXT PREVIEW:\n%s", po_text[:300])

    if not invoice_text.strip():
        return {"discrepancies": [], "summary": "", "error": "Invoice text is empty after extraction."}
    if not po_text.strip():
        return {"discrepancies": [], "summary": "", "error": "PO text is empty after extraction."}

    # Stage 2: LLM comparison
    comparison = compare_invoice_po(invoice_text, po_text)
    logger.info(
        "PIPELINE STAGE 2 — LLM: %d discrepancy(ies), error=%s",
        len(comparison.get("discrepancies", [])),
        comparison.get("error"),
    )

    return {
        "invoice_text": invoice_text,
        "po_text": po_text,
        "discrepancies": comparison.get("discrepancies", []),
        "summary": comparison.get("summary", ""),
        "error": comparison.get("error"),
    }


def _ui_status(result: dict) -> str:
    if result.get("error"):
        return "Error"
    if result.get("discrepancies"):
        return "Discrepancies Found"
    return "Matched ✅"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/upload")
def upload_page():
    return render_template("upload.html", result_json={}, status="Pending")


@app.route("/verify", methods=["POST"])
def verify_route():
    invoice_bytes, invoice_name = _read_upload("invoiceFile")
    po_bytes, po_name = _read_upload("poFile")

    if invoice_bytes is None:
        return render_template("upload.html", result_json={"error": "Missing or invalid invoice file."}, status="Error")
    if po_bytes is None:
        return render_template("upload.html", result_json={"error": "Missing or invalid PO file."}, status="Error")

    result = _run_pipeline(invoice_bytes, invoice_name, po_bytes, po_name)
    status = _ui_status(result)

    report = {
        "status": status,
        "discrepancies": result["discrepancies"],
        "summary": result.get("summary", ""),
    }
    if result.get("error"):
        report["error"] = result["error"]

    return render_template("upload.html", result_json=report, status=status)


@app.route("/api/verify-invoice", methods=["POST"])
def verify_invoice_json():
    # Accept both field-name variants for backward compatibility
    invoice_bytes, invoice_name = (
        _read_upload("invoice_pdf") or (None, None)
        if not request.files.get("invoiceFile")
        else _read_upload("invoiceFile")
    )
    po_bytes, po_name = (
        _read_upload("po_pdf") or (None, None)
        if not request.files.get("poFile")
        else _read_upload("poFile")
    )

    # Try the other field name if the first is None
    if invoice_bytes is None:
        invoice_bytes, invoice_name = _read_upload("invoice_pdf")
    if po_bytes is None:
        po_bytes, po_name = _read_upload("po_pdf")

    if invoice_bytes is None:
        return jsonify({"error": "Missing invoice PDF (use invoice_pdf or invoiceFile)."}), 400
    if po_bytes is None:
        return jsonify({"error": "Missing PO PDF (use po_pdf or poFile)."}), 400

    result = _run_pipeline(invoice_bytes, invoice_name, po_bytes, po_name)

    if result.get("error"):
        return jsonify({"error": result["error"], "discrepancies": []}), 422

    return jsonify({
        "invoice_text": result["invoice_text"],
        "po_text": result["po_text"],
        "discrepancies": result["discrepancies"],
        "summary": result.get("summary", ""),
    })


# ---------------------------------------------------------------------------
# Gmail / OAuth (unchanged)
# ---------------------------------------------------------------------------

@app.route("/check_gmail")
def check_gmail():
    credentials = None
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                CLIENT_SECRETS_FILE,
                scopes=SCOPES,
                redirect_uri=url_for("oauth2callback", _external=True),
            )
            authorization_url, state = flow.authorization_url(
                access_type="offline", include_granted_scopes="true"
            )
            session["oauth_state"] = state
            return redirect(authorization_url)

    return jsonify({"status": "Gmail scan not fully enabled in this demo build."})


@app.route("/oauth2callback")
def oauth2callback():
    state = session.get("oauth_state")
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for("oauth2callback", _external=True),
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    with open(CREDENTIALS_FILE, "wb") as token:
        pickle.dump(credentials, token)
    return redirect(url_for("check_gmail"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)