import sys

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_route = """@app.route("/verify", methods=["POST"])
def verify_route():
    logger.info("CALL CHAIN /verify -> extract_text_from_pdf(invoice) -> extract_text_from_pdf(po) -> compare_invoice_po")
    # 1) CHECK BOTH FILES EXIST
    invoice_file = request.files.get("invoice")
    po_file = request.files.get("purchase_order")

    if not invoice_file or not po_file:
        return jsonify({"error": True, "message": "Please upload both PDF files."}), 400

    # 2) CHECK FILE EXTENSION (.pdf only)
    if not (invoice_file.filename or "").lower().endswith(".pdf") or not (po_file.filename or "").lower().endswith(".pdf"):
        return jsonify({"error": True, "message": "Please upload PDF files only."}), 400

    # 3) CHECK PDF MAGIC BYTES (%PDF)
    invoice_header = invoice_file.stream.read(4)
    po_header = po_file.stream.read(4)
    invoice_file.stream.seek(0)
    po_file.stream.seek(0)

    if invoice_header != b"%PDF" or po_header != b"%PDF":
        return jsonify({"error": True, "message": "Invalid PDF file detected."}), 400

    # 4) CHECK FILE SIZE (max 10MB each)
    MAX_FILE_SIZE = 10 * 1024 * 1024

    invoice_file.stream.seek(0, os.SEEK_END)
    invoice_size = invoice_file.stream.tell()
    invoice_file.stream.seek(0)

    po_file.stream.seek(0, os.SEEK_END)
    po_size = po_file.stream.tell()
    po_file.stream.seek(0)

    if invoice_size > MAX_FILE_SIZE or po_size > MAX_FILE_SIZE:
        return jsonify({"error": True, "message": "File size must be under 10MB."}), 400

    # 5) WRAP OCR + COMPARISON CALLS IN TRY/EXCEPT
    try:
        logger.info("CALL CHAIN /verify -> OCR extraction start for invoice")
        invoice_text = extract_text_from_pdf(invoice_file.stream.read())
        logger.info("CALL CHAIN /verify -> OCR extraction complete for invoice chars=%d", len(invoice_text))
        logger.info("CALL CHAIN /verify -> OCR extraction start for purchase_order")
        po_text = extract_text_from_pdf(po_file.stream.read())
        logger.info("CALL CHAIN /verify -> OCR extraction complete for purchase_order chars=%d", len(po_text))

        if len(invoice_text.strip()) < 20 or len(po_text.strip()) < 20:
            return jsonify({"error": True, "message": "Could not read the PDF properly. Please upload a clear file."}), 422

        logger.info("CALL CHAIN /verify -> compare_invoice_po invoice_length=%d po_length=%d", len(invoice_text), len(po_text))
        result = compare_invoice_po(invoice_text, po_text)
    except Exception as e:
        logger.error("VERIFY ROUTE ERROR: %s", str(e))
        return jsonify({"error": True, "message": "We could not process these documents. Please try again."}), 500

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
        return jsonify({"error": True, "message": result.get("error")}), 422
    
    if len(discrepancies) > 0:
        status = "Discrepancies Found"
    else:
        status = "No Discrepancies Found"

    return jsonify({
        "status": status,
        "total_issues": len(discrepancies),
        "total_rupee_difference": total_difference,
        "discrepancies": discrepancies
    })
"""

# The verify_route definition starts at line 183 and ends at line 284.
# (Index 182 to 284 in 0-indexed python list)
start_idx = 182
end_idx = 284

lines[start_idx:end_idx] = [line + '\n' for line in new_route.split('\n')]

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
