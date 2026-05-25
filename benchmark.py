from __future__ import annotations
import os
import sys
import time
import json
from datetime import datetime

# Ensure Verifix root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from parser.line_items import extract_line_items_with_diagnostics
from llm import compare_invoice_po
from ocr.extract import extract_text_from_pdf
from tests.conftest import (
    CLEAN_INVOICE_OCR,
    CLEAN_PO_OCR,
    CORRUPTED_OCR_TEXT,
    BLURRY_OCR_TEXT,
    GST_INVOICE_OCR,
    DUPLICATE_ITEMS_OCR,
    MISSING_ITEMS_INVOICE_OCR,
    MISSING_ITEMS_PO_OCR,
    EMPTY_OCR_TEXT,
    TOO_SHORT_OCR_TEXT,
    COORDINATE_GARBAGE_TEXT,
    make_minimal_pdf
)

def run_verifix_benchmarks():
    print("=" * 75)
    print("                 VERIFIX OCR & PARSER ACCURACY BENCHMARK                ")
    print("=" * 75)

    os.makedirs("benchmark_results", exist_ok=True)
    
    # 1. MEASURE RAW OCR LATENCY (Scanned/Digital rendering simulation)
    print("1. Measuring raw OCR engine performance (pypdfium2 + Tesseract/PaddleOCR)...")
    t0 = time.perf_counter()
    dummy_pdf = make_minimal_pdf("VERIFIX BENCHMARK PDF CONTENT")
    _ = extract_text_from_pdf(dummy_pdf)
    ocr_latency_ms = (time.perf_counter() - t0) * 1000
    print(f"   [OCR LATENCY] End-to-end PDF render + OCR pass: {ocr_latency_ms:.2f} ms")
    print("-" * 75)

    # 2. BENCHMARK SCENARIOS DEFINITIONS WITH GROUND TRUTHS
    scenarios = [
        {
            "id": "clean_digital",
            "category": "Clean Digital PDF",
            "invoice_text": CLEAN_INVOICE_OCR,
            "po_text": CLEAN_PO_OCR,
            "expected_items": {
                "laptop": {"qty": 10, "price": 45000},
                "mouse": {"qty": 20, "price": 500},
                "monitor": {"qty": 5, "price": 12000},
                "keyboard": {"qty": 15, "price": 800}
            },
            "expected_discrepancies_count": 0
        },
        {
            "id": "scanned_invoice",
            "category": "Scanned Invoice (Corrupted)",
            "invoice_text": CORRUPTED_OCR_TEXT,
            "po_text": CLEAN_PO_OCR,
            # We expect numeric homoglyph recovery to match clean values
            "expected_items": {
                "laptop": {"qty": 10, "price": 45000},
                "mouse": {"qty": 20, "price": 500},
                "monitor": {"qty": 5, "price": 12000},
                "keyboard": {"qty": 15, "price": 800}
            },
            "expected_discrepancies_count": 0
        },
        {
            "id": "blurry_scan",
            "category": "Blurry Scan",
            "invoice_text": BLURRY_OCR_TEXT,
            "po_text": CLEAN_PO_OCR,
            "expected_items": {
                "laptop": {"qty": 10, "price": 45000},
                "monitor": {"qty": 5, "price": 12000}
            },
            "expected_discrepancies_count": 2  # Mouse and Keyboard missing
        },
        {
            "id": "gst_heavy",
            "category": "GST-Heavy Invoice",
            "invoice_text": GST_INVOICE_OCR,
            "po_text": GST_INVOICE_OCR,
            "expected_items": {
                "office chair": {"qty": 10, "price": 5000},
                "desk": {"qty": 5, "price": 12000},
                "filing cab": {"qty": 3, "price": 8000}
            },
            "expected_discrepancies_count": 0
        },
        {
            "id": "duplicate_items",
            "category": "Duplicate Item Invoice",
            "invoice_text": DUPLICATE_ITEMS_OCR,
            "po_text": CLEAN_PO_OCR,
            "expected_items": {
                "laptop": {"qty": 5, "price": 45000},
                "mouse": {"qty": 10, "price": 500}
            },
            "expected_discrepancies_count": 1 # Laptop duplicate
        },
        {
            "id": "missing_items",
            "category": "Missing Item Case",
            "invoice_text": MISSING_ITEMS_INVOICE_OCR,
            "po_text": MISSING_ITEMS_PO_OCR,
            "expected_items": {
                "laptop": {"qty": 10, "price": 45000},
                "mouse": {"qty": 20, "price": 500}
            },
            "expected_discrepancies_count": 2 # Monitor & Keyboard missing
        },
        {
            "id": "malformed_empty",
            "category": "Malformed Empty OCR",
            "invoice_text": EMPTY_OCR_TEXT,
            "po_text": CLEAN_PO_OCR,
            "expected_items": {},
            "expected_discrepancies_count": 0 # Empty input early returns
        },
        {
            "id": "too_short",
            "category": "Malformed Too Short",
            "invoice_text": TOO_SHORT_OCR_TEXT,
            "po_text": CLEAN_PO_OCR,
            "expected_items": {},
            "expected_discrepancies_count": 0
        }
    ]

    report_details = []
    total_scenarios = len(scenarios)
    successful_runs = 0
    fallback_triggers = 0
    total_price_accuracy = 0.0
    total_qty_accuracy = 0.0
    total_discrepancy_accuracy = 0.0
    
    # Timing variables accumulator
    sum_parser_time = 0.0
    sum_recon_time = 0.0
    sum_total_time = 0.0

    print("2. Running offline extraction & comparison scenarios...")
    print("-" * 75)

    for sc in scenarios:
        sc_id = sc["id"]
        category = sc["category"]
        invoice = sc["invoice_text"]
        po = sc["po_text"]
        expected_items = sc["expected_items"]
        expected_discrepancies_count = sc["expected_discrepancies_count"]

        # Run pipeline and measure latency
        t_start = time.perf_counter()
        
        # Timing parser explicitly
        t_parse_start = time.perf_counter()
        inv_diag = extract_line_items_with_diagnostics(invoice)
        t_parse_end = time.perf_counter()
        parser_latency = (t_parse_end - t_parse_start) * 1000
        sum_parser_time += parser_latency

        # Timing full end-to-end request
        result = compare_invoice_po(invoice, po)
        total_request_time = (time.perf_counter() - t_start) * 1000
        sum_total_time += total_request_time
        
        recon_latency = max(total_request_time - parser_latency * 2, 0.1)
        sum_recon_time += recon_latency

        parsed_items = result.get("invoice_items", [])
        discrepancies = result.get("discrepancies", [])
        confidence_flags = result.get("confidence_flags", [])
        
        # Check fallback triggers
        fallback_used = result.get("invoice_parser", {}).get("fallback_used", False) or result.get("po_parser", {}).get("fallback_used", False)
        if fallback_used or "OCR_FALLBACK_TRIGGERED" in confidence_flags:
            fallback_triggers += 1

        # Accuracy Calculations
        matched_items_count = 0
        correct_qty = 0
        correct_price = 0
        
        parsed_item_map = {}
        for item in parsed_items:
            name = item.get("item", "").lower().strip()
            parsed_item_map[name] = item

        for gt_name, gt_vals in expected_items.items():
            # Find closest item match
            matched_key = None
            for parsed_name in parsed_item_map:
                if gt_name in parsed_name or parsed_name in gt_name:
                    matched_key = parsed_name
                    break
            
            if matched_key:
                matched_items_count += 1
                parsed_val = parsed_item_map[matched_key]
                if parsed_val.get("qty") == gt_vals["qty"]:
                    correct_qty += 1
                if parsed_val.get("price") == gt_vals["price"]:
                    correct_price += 1

        # Normalized scenario percentages
        denom = max(len(expected_items), 1)
        item_qty_accuracy = (correct_qty / denom) * 100
        item_price_accuracy = (correct_price / denom) * 100
        
        # Discrepancy accuracy
        actual_disc_count = len(discrepancies)
        if expected_discrepancies_count == 0:
            disc_accuracy = 100.0 if actual_disc_count == 0 else max(0.0, 100.0 - actual_disc_count * 25.0)
        else:
            disc_accuracy = (1.0 - abs(actual_disc_count - expected_discrepancies_count) / expected_discrepancies_count) * 100
            disc_accuracy = max(0.0, disc_accuracy)

        total_qty_accuracy += item_qty_accuracy
        total_price_accuracy += item_price_accuracy
        total_discrepancy_accuracy += disc_accuracy
        successful_runs += 1

        report_details.append({
            "scenario_id": sc_id,
            "category": category,
            "latency_parser_ms": round(parser_latency, 2),
            "latency_reconciliation_ms": round(recon_latency, 2),
            "total_request_time_ms": round(total_request_time, 2),
            "fallback_triggered": fallback_used,
            "confidence_flags": confidence_flags,
            "quantity_accuracy": round(item_qty_accuracy, 2),
            "price_accuracy": round(item_price_accuracy, 2),
            "discrepancy_accuracy": round(disc_accuracy, 2),
            "parsed_items_count": len(parsed_items),
            "expected_items_count": len(expected_items),
            "actual_discrepancies_count": actual_disc_count,
            "expected_discrepancies_count": expected_discrepancies_count
        })

    # Summary metrics averages
    avg_qty_accuracy = total_qty_accuracy / total_scenarios
    avg_price_accuracy = total_price_accuracy / total_scenarios
    avg_disc_accuracy = total_discrepancy_accuracy / total_scenarios
    fallback_rate = (fallback_triggers / total_scenarios) * 100
    
    avg_parser_ms = sum_parser_time / total_scenarios
    avg_recon_ms = sum_recon_time / total_scenarios
    avg_total_ms = sum_total_time / total_scenarios

    # Write JSON report
    report_meta = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_scenarios": total_scenarios,
            "average_quantity_accuracy": round(avg_qty_accuracy, 2),
            "average_price_accuracy": round(avg_price_accuracy, 2),
            "average_discrepancy_accuracy": round(avg_disc_accuracy, 2),
            "fallback_activation_rate_pct": round(fallback_rate, 2),
            "avg_ocr_latency_ms": round(ocr_latency_ms, 2),
            "avg_parser_latency_ms": round(avg_parser_ms, 2),
            "avg_reconciliation_latency_ms": round(avg_recon_ms, 2),
            "avg_total_request_latency_ms": round(avg_total_ms, 2)
        },
        "details": report_details
    }

    report_filename = f"benchmark_results/benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_filename, "w", encoding="utf-8") as f:
        json.dump(report_meta, f, indent=2, ensure_ascii=False)

    # 3. PRINT BEAUTIFUL CONSOLE BENCHMARK SUMMARY TABLE
    print("\n" + "=" * 80)
    print("                     VERIFIX METRICS SUMMARY TABLES                     ")
    print("=" * 80)
    print(f"{'Category':<30} | {'Qty Acc%':<10} | {'Price Acc%':<10} | {'Recon Acc%':<10} | {'Latency':<10}")
    print("-" * 80)
    for row in report_details:
        lat_str = f"{row['total_request_time_ms']:.1f}ms"
        print(f"{row['category']:<30} | {row['quantity_accuracy']:<10.1f} | {row['price_accuracy']:<10.1f} | {row['discrepancy_accuracy']:<10.1f} | {lat_str:<10}")
    print("-" * 80)
    print(f"{'AVERAGES / TOTALS':<30} | {avg_qty_accuracy:<10.1f} | {avg_price_accuracy:<10.1f} | {avg_disc_accuracy:<10.1f} | {avg_total_ms:.1f}ms")
    print("=" * 80)

    print("\n" + "=" * 80)
    print("                    LATENCY & EXTRACTION DIAGNOSTICS                    ")
    print("=" * 80)
    print(f"  - Simulated OCR Latency        : {ocr_latency_ms:.2f} ms")
    print(f"  - Average Parser Latency       : {avg_parser_ms:.2f} ms")
    print(f"  - Average Reconciliation Engine : {avg_recon_ms:.2f} ms")
    print(f"  - Average End-to-End Latency   : {avg_total_ms:.2f} ms")
    print(f"  - OCR Fallback Trigger Rate    : {fallback_rate:.1f}%")
    print(f"  - Detailed JSON Report Saved To: {report_filename}")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_verifix_benchmarks()
