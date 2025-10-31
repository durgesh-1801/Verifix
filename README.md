# Verifix
VerifiX is an AI-driven FinTech solution that automates the invoice and purchase order (PO) verification process, reducing manual effort, errors, and financial discrepancies. The system intelligently extracts key data, compares entries, flags mismatches, and exports verified results
# FuturixAI FinVerify

> [cite_start]**Note:** This project was built for the **HackX 3.0 Hackathon** [cite: 13][cite_start], solving the FINTECH problem statement: "Al-Powered Invoice and Purchase Order Verification System" [cite: 332] [cite_start]sponsored by **FuturixAI**[cite: 25, 332].

An intelligent financial operations tool that uses AI to automate Purchase Order (PO) and Invoice verification. This app detects discrepancies in seconds, saving time and preventing costly accounting errors.

---





---

## 🎯 The Problem

Manually verifying financial documents is slow, tedious, and prone to human error. Finance teams must compare Purchase Orders against Invoices line-by-line to check for mismatches in prices or quantities. This can lead to overpayments, duplicate payments, and wasted employee time.

## 💡 The Solution

**FuturixAI FinVerify** is a web application that solves this by:
1.  [cite_start]**Extracting Data:** Using the **FuturixAI Shivaay LLM**[cite: 32], our app reads any unstructured document (PDF, image, or text file) and instantly extracts structured JSON data.
2.  **Verifying Documents:** It performs an automated **2-Way Match**, comparing the PO and Invoice JSON data to find any discrepancies.
3.  **Reporting Results:** It instantly provides the user with a clean report showing a "Matched" status or a "Flagged" status with a table of all mismatches.

---

## ✨ Key Features

* **🤖 AI-Powered Data Extraction:** Leverages the sponsor's **Shivaay LLM** to parse unstructured documents (PDFs, .txt, .png, etc.) into clean JSON, regardless of the document's layout.
* **📊 Automated 2-Way Matching:** Instantly compares the extracted PO and Invoice data to find discrepancies in:
    * Total Amount
    * Vendor Name
    * Line Item Quantities
* **📋 Clear Verification Report:** A user-friendly frontend that displays a "Matched" ✅ or "Flagged" 🚩 status, along with a detailed table of any mismatches found.
* **📤 Manual Upload:** A simple drag-and-drop interface for users to upload their PO and Invoice files directly.
* **📧 (Bonus) Gmail Automation:** A "Scan My Gmail" feature that uses the Google API to:
    1.  Securely log in to a user's Gmail account.
    2.  Find emails with PO and Invoice attachments.
    3.  Automatically run the verification process on those attachments.

---

## 🛠️ Tech Stack

* **Backend:** **Python**, **Flask** (for the web server and API)
* **Frontend:** **HTML5**, **CSS3**, **JavaScript** (using `fetch` for API calls)
* [cite_start]**AI (Sponsor Tech):** **FuturixAI Shivaay LLM API** (via the `openai` Python library) [cite: 32]
* **External APIs:** **Google Gmail API** (using `google-api-python-client` for the bonus feature)

---

## 🚀 How to Run This Project Locally

### 1. Prerequisites

* Python 3.10+
* A Google Cloud project with the **Gmail API** enabled.
* A `client_secret.json` file from your Google Cloud project.
* An API Key and Base URL from **FuturixAI**.

### 2. Setup

**Step 1: Clone the repository**
```bash
git clone [https://github.com/your-username/futurixai-finverify.git](https://github.com/your-username/futurixai-finverify.git)
cd futurixai-finverify
```

**Step 2: Install Python dependencies**
```bash
pip install -r requirements.txt
```
*(You will need to create a `requirements.txt` file. Based on our chat, it should contain:)*
```
Flask
flask-cors
openai
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
```

**Step 3: Add Google API Credentials**
* Download your `client_secret.json` file from the Google Cloud Console.
* Place it in the root of the `HACKX` folder, next to `app.py`.

**Step 4: Set Environment Variables**
This is the most important step. You must set these in your terminal *before* running the app.

*On Windows (Command Prompt):*
```bash
set FUTURIXAI_API_KEY="your-shivaay-api-key"
set FUTURIXAI_API_BASE="httpss://[shivaay.futurixai.com/playground](https://shivaay.futurixai.com/playground)"
```

*On macOS/Linux:*
```bash
export FUTURIXAI_API_KEY="your-shivaay-api-key"
export FUTURIXAI_API_BASE="httpss://[shivaay.futurixai.com/playground](https://shivaay.futurixai.com/playground)"
```

**Step 5: Run the Flask Server**
*Make sure you are running the correct file (e.g., `app.py`).*
```bash
python app.py
```

**Step 6: Open the App**
* Your server is now running. Open your browser and go to:
* **`http://127.0.0.1:5000/`**

---

## 🔮 Future Improvements

* **3-Way Matching:** Add support for uploading a "Receiving Report" or "Packing Slip" to verify that the items were not only ordered and billed, but also delivered.
* **Results Dashboard:** Create a database to save all verification reports and display a dashboard of common discrepancies, top vendors, and overall accuracy.
* **Full Email Automation:** Create a background worker that scans the Gmail inbox every 10 minutes and sends an email alert when a discrepancy is found.
