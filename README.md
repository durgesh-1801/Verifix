# 🧾 Verifix (AI-Powered Invoice & Purchase Order Verification System) 
### Built for MUJ HACKX 3.0 | Theme: FinTech  
#### By Team **Quantum Crew**

---

## 🚀 Overview

This project automates the **manual verification of invoices and purchase orders (POs)** using **AI and LLM technology**.  
It extracts key information, detects mismatches, and improves financial transparency — eliminating human error and saving valuable time.

> 💡 Manual verification is time-consuming, error-prone, and expensive.  
> Our AI-powered solution performs instant validation between invoice and purchase order data using the **Shivaay LLM API**.

---

## 🎯 Problem Statement

> **PS #6:** AI-Powered Invoice and Purchase Order Verification System (Futurix AI)

**Challenge:**  
Manual verification of invoices and purchase orders is tedious and prone to errors.  
Finance teams often face issues such as mismatched entries, incorrect totals, and vendor discrepancies.

**Goal:**  
To develop an **AI-powered tool** that automatically extracts and reconciles data between invoices and purchase orders, detects mismatches, and ensures accurate financial reporting.

---

## 🧠 Key Features

- 🤖 **AI Verification using Shivaay LLM API**  
  Automatically detects inconsistencies between invoice and PO.

- 🧾 **Data Extraction**  
  Extracts vendor name, total amount, quantity, and transaction date.

- ⚠️ **Discrepancy Detection**  
  Instantly flags mismatches (amounts, vendor names, line items, etc.).

- 📧 **Gmail Integration**  
  Scans Gmail inbox using the Gmail API to detect potential invoice/PO pairs.

- 💾 **CSV Export (Upcoming)**  
  For easy accounting or ERP integration.

- 🧱 **Fallback Mode**  
  Works with mock AI logic even when the API or internet is unavailable.

- 🎨 **Modern UI**  
  Simple Bootstrap interface for uploading and verifying files.

---

## 🏗️ Architecture Overview

```text
+--------------------------+
|   User Uploads Files     |
|  (Invoice & PO in .txt)  |
+-----------+--------------+
            |
            v
+--------------------------+
|  Flask Backend (Python)  |
|  → Calls Shivaay LLM API |
+-----------+--------------+
            |
            v
+--------------------------+
| AI Response Verification |
|   → Finds Discrepancies  |
+-----------+--------------+
            |
            v
+--------------------------+
|  Result Rendered in UI   |
|  + Gmail Automation Tab  |
+--------------------------+
---
**Additional Tools & Libraries:**
- `Flask-CORS` — to enable cross-origin requests between frontend and backend  
- `Requests` — for making API calls to Shivaay LLM  
- `Google API Python Client` — for Gmail automation  
- `Bootstrap` — for responsive and modern UI  
- `Jinja2` — for rendering dynamic templates in Flask
```


