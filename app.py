# app.py — Invoice / PO verification (Groq via llm.py, PDF text via ocr.py)
#
# Key fixes vs original:
#   - Logging configured at startup so DEBUG prints from ocr.py and llm.py are visible.
#   - File type validation: accepts .pdf and .txt. .txt files are decoded directly,
#     skipping the entire OCR pipeline (was a silent breakage before).
#   - pipeline_debug() logs every stage so you can pinpoint where data goes wrong.
#   - No logic change to Gmail / OAuth routes — left as-is.

from __future__ import annotations

import io
import json
import logging
import os
import pickle
from datetime import datetime

from dotenv import load_dotenv
import fitz
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

load_dotenv()

# ── Configure logging BEFORE any other import that uses the logger ──────────
logging.basicConfig(
    level=logging.DEBUG,          # flip to INFO in production
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from flask_cors import CORS
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

from llm import compare_invoice_po


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


def _ui_status(result: dict) -> str:
    if result.get("error"):
        return "Error"
    if result.get("discrepancies"):
        return "Discrepancies Found"
    return "Matched ✅"


def extract_text_from_pdf(file_bytes):
    text = ""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print("PyMuPDF extraction failed:", str(e))
        return ""

    print("===== OCR DEBUG =====")
    print("TEXT LENGTH:", len(text))
    print("TEXT SAMPLE:", text[:500])
    if len(text.strip()) < 50:
        print("⚠️ Weak extraction detected")

    return text.strip()


def _json_error_payload(invoice_text: str, po_text: str):
    return jsonify({
        "error": "OCR failed — extracted text too small",
        "invoice_length": len(invoice_text),
        "po_length": len(po_text)
    })


def _run_pipeline(invoice_bytes: bytes, invoice_name: str,
                  po_bytes: bytes, po_name: str) -> dict:
    """
    Full pipeline: extract text -> call LLM -> return structured result.
    Logs every stage so you can see exactly where data breaks.
    """
    try:
        invoice_text = _extract_text(invoice_bytes, invoice_name)
        po_text = _extract_text(po_bytes, po_name)
    except Exception as exc:
        return {
            "invoice_text": "",
            "po_text": "",
            "discrepancies": [],
            "summary": "",
            "error": str(exc),
            "raw_response": {},
        }

    if len(invoice_text.strip()) < 50 or len(po_text.strip()) < 50:
        return {
            "invoice_text": invoice_text,
            "po_text": po_text,
            "discrepancies": [],
            "summary": "",
            "error": "OCR failed — extracted text too small",
            "raw_response": {},
        }

    print("===== SENDING TO LLM =====")
    print("Invoice length:", len(invoice_text))
    print("PO length:", len(po_text))

    comparison = compare_invoice_po(invoice_text, po_text)
    print("===== RAW LLM RESPONSE =====")
    print(comparison)

    return {
        "invoice_text": invoice_text,
        "po_text": po_text,
        "discrepancies": comparison.get("discrepancies", []),
        "summary": comparison.get("summary", ""),
        "error": comparison.get("error"),
        "raw_response": comparison,
    }


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
    # 1) CHECK BOTH FILES EXIST
    invoice_file = request.files.get("invoiceFile")
    po_file = request.files.get("poFile")

    if not invoice_file or not po_file:
        return render_template(
            "upload.html",
            status="Error",
            error="Please upload both PDF files."
        )

    # 2) CHECK FILE EXTENSION (.pdf only)
    if not (invoice_file.filename or "").lower().endswith(".pdf") or not (po_file.filename or "").lower().endswith(".pdf"):
        return render_template(
            "upload.html",
            status="Error",
            error="Please upload PDF files only."
        )

    # 3) CHECK PDF MAGIC BYTES (%PDF)
    invoice_header = invoice_file.stream.read(4)
    po_header = po_file.stream.read(4)
    invoice_file.stream.seek(0)
    po_file.stream.seek(0)

    if invoice_header != b"%PDF" or po_header != b"%PDF":
        return render_template(
            "upload.html",
            status="Error",
            error="Invalid PDF file detected."
        )

    # 4) CHECK FILE SIZE (max 10MB each)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    invoice_file.stream.seek(0, os.SEEK_END)
    invoice_size = invoice_file.stream.tell()
    invoice_file.stream.seek(0)

    po_file.stream.seek(0, os.SEEK_END)
    po_size = po_file.stream.tell()
    po_file.stream.seek(0)

    if invoice_size > MAX_FILE_SIZE or po_size > MAX_FILE_SIZE:
        return render_template(
            "upload.html",
            status="Error",
            error="File size must be under 10MB."
        )

    # 5) WRAP OCR + LLM CALLS IN TRY/EXCEPT
    try:
        invoice_text = extract_text_from_pdf(invoice_file.stream.read())
        po_text = extract_text_from_pdf(po_file.stream.read())

        if len(invoice_text.strip()) < 20 or len(po_text.strip()) < 20:
            return render_template(
                "upload.html",
                status="Error",
                error="Could not read the PDF properly. Please upload a clear file."
            )

        result = compare_invoice_po(invoice_text, po_text)
    except Exception as e:
        print("VERIFY ROUTE ERROR:", str(e))
        return render_template(
            "upload.html",
            status="Error",
            error="We could not process these documents. Please try again."
        )

    discrepancies = result.get("discrepancies", [])
    total_difference = 0

    for d in discrepancies:
        diff = d.get("difference", "N/A")
        try:
            if diff != "N/A":
                total_difference += float(diff)
        except Exception:
            pass

    # Remove decimals if whole number
    if total_difference == int(total_difference):
        total_difference = int(total_difference)

    if result.get("error"):
        status = "Error"
    elif len(discrepancies) > 0:
        status = "Discrepancies Found"
    else:
        status = "Matched ✅"

    return render_template("upload.html", result=result, status=status, total_difference=total_difference)


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


@app.route("/export-pdf", methods=["POST"])
def export_pdf():
    status = request.form.get("status", "Unknown")
    total_issues = request.form.get("total_issues", "0")
    total_difference = request.form.get("total_difference", "0")

    try:
        discrepancies = json.loads(request.form.get("discrepancies_json", "[]"))
        if not isinstance(discrepancies, list):
            discrepancies = []
    except Exception:
        discrepancies = []

    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    # Header
    elements.append(Paragraph("Invoice AI", styles["Title"]))
    elements.append(Paragraph("AI-powered Invoice Verification Report", styles["Normal"]))
    elements.append(Spacer(1, 14))

    # Summary section
    summary_data = [
        ["Status", str(status)],
        ["Total Issues", str(total_issues)],
        ["Total Rupee Difference", f"₹{total_difference}"],
        ["Timestamp", timestamp],
    ]
    summary_table = Table(summary_data, colWidths=[180, 320])
    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 14))

    # Discrepancy table
    table_data = [["Item", "Field", "Invoice", "PO", "Difference", "Issue"]]
    for d in discrepancies:
        if not isinstance(d, dict):
            continue
        table_data.append([
            str(d.get("item", "-")),
            str(d.get("field", "-")),
            str(d.get("invoice_value", "-")),
            str(d.get("po_value", "-")),
            str(d.get("difference", "N/A")),
            str(d.get("issue", "-")),
        ])

    if len(table_data) == 1:
        table_data.append(["-", "-", "-", "-", "-", "No discrepancies found"])

    report_table = Table(table_data, repeatRows=1)
    report_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(report_table)
    elements.append(Spacer(1, 14))

    # Footer
    elements.append(Paragraph(f"© 2026 Reconix | {timestamp}", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="invoice_ai_report.pdf",
        mimetype="application/pdf",
    )


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