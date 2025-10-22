#!/usr/bin/env python3
"""
Test suite for Universal Credit Card Statement Parser (SBI/HDFC)

- Runs the universal parser against a set of PDFs
- Prints a human-friendly summary + quality report
- Saves each result as JSON **directly under services/** by default
"""

from __future__ import annotations

import os
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path

CUR_DIR = Path(__file__).resolve().parent  # -> services/
sys.path.insert(0, str(CUR_DIR))

try:
    from universal_credit_card_parser import UniversalCreditCardParser, format_output
except Exception as e:
    print(f"❌ Import Error: {e}")
    print("💡 Make sure universal_credit_card_parser.py is in the same directory as test.py")
    sys.exit(1)

FIELDS_TO_CHECK = [
    "card_variant",
    "card_last_4_digits",
    "billing_cycle",
    "payment_due_date",
    "total_amount_due",
]

def display_statement(result: dict) -> None:
    print("\n📊 STATEMENT SUMMARY")
    print("=" * 70)
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return

    print(f"   🏦 Issuer: {result.get('issuer', 'Unknown')}")
    if result.get("card_variant"):
        print(f"   💳 Card Variant: {result.get('card_variant')}")
    if result.get("card_last_4_digits"):
        print(f"   🔢 Card Number: **** **** **** {result.get('card_last_4_digits')}")
    if result.get("billing_cycle"):
        print(f"   📅 Billing Cycle: {result.get('billing_cycle')}")
    if result.get("payment_due_date"):
        print(f"   ⏰ Payment Due Date: {result.get('payment_due_date')}")
    if result.get("total_amount_due"):
        print(f"   💰 Total Amount Due: {result.get('total_amount_due')}")
    txns = result.get("transactions", [])
    print(f"   📋 Transactions: {len(txns)} found")
    if txns:
        print("\n💳 SAMPLE TRANSACTIONS (first 5):")
        print("-" * 70)
        for i, txn in enumerate(txns[:5], 1):
            if isinstance(txn, dict):
                date = txn.get("date", "N/A")
                desc = str(txn.get("description", "N/A"))
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                amount = txn.get("amount", "N/A")
                print(f"   {i}. {date} | {desc} | {amount}")
            else:
                s = str(txn)
                if len(s) > 70:
                    s = s[:67] + "..."
                print(f"   {i}. {s}")
        if len(txns) > 5:
            print(f"\n   ... and {len(txns) - 5} more")

def validate_extraction(result: dict) -> dict:
    if "error" in result:
        return {
            "success": False,
            "score": 0,
            "fields_extracted": 0,
            "total_fields": len(FIELDS_TO_CHECK),
            "percentage": 0.0,
            "has_transactions": False,
            "transaction_count": 0,
        }
    fields_extracted = sum(1 for f in FIELDS_TO_CHECK if result.get(f))
    total_fields = len(FIELDS_TO_CHECK)
    percentage = (fields_extracted / total_fields) * 100 if total_fields else 0.0
    txns = result.get("transactions") or []
    return {
        "success": True,
        "score": fields_extracted,
        "fields_extracted": fields_extracted,
        "total_fields": total_fields,
        "percentage": percentage,
        "has_transactions": bool(txns),
        "transaction_count": len(txns),
    }

def print_validation_report(validation: dict) -> None:
    print("\n📈 EXTRACTION QUALITY REPORT")
    print("-" * 70)
    if not validation.get("success"):
        print("❌ Parsing failed - no data extracted")
        return
    pct = validation["percentage"]
    print(f"   Extraction Rate: {pct:.1f}% ({validation['fields_extracted']}/{validation['total_fields']})")
    bar_len = 30
    filled = int(bar_len * pct / 100.0)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"   [{bar}]")
    if pct == 100:
        print("   🎉 Perfect extraction!")
    elif pct >= 80:
        print("   ✨ Good extraction!")
    elif pct >= 60:
        print("   ⚠️  Partial extraction - some fields missing")
    else:
        print("   ❌ Poor extraction - review parser logic")
    if validation["has_transactions"]:
        print(f"   ✅ Transactions: {validation['transaction_count']} found")
    else:
        print("   ⚠️  Transactions: None found")

def save_to_json(result: dict, pdf_file: str, out_dir: Path) -> Path:
    """
    Save JSON **directly under services/** by default (no subfolder).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    issuer = (result.get("issuer") or "unknown").lower()
    last4 = result.get("card_last_4_digits") or "xxxx"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(pdf_file).stem
    fname = f"{issuer}_{last4}_{base}_{ts}.json"
    path = out_dir / fname
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path

def test_single_file(parser: UniversalCreditCardParser, pdf_file: str, issuer: str | None) -> dict:
    print("\n" + "=" * 100)
    print(f"📄 Processing: {pdf_file}")
    print("=" * 100)
    if not os.path.exists(pdf_file):
        print("⏭️  Skipped (file not found)")
        return {"file": pdf_file, "status": "SKIPPED", "json": None, "validation": None}
    try:
        result = parser.parse(pdf_file, issuer)
        print(format_output(result, "pretty"))
        display_statement(result)
        validation = validate_extraction(result)
        print_validation_report(validation)
        # Save IN services/ (CUR_DIR)
        json_path = save_to_json(result, pdf_file, CUR_DIR)
        print(f"\n💾 Saved JSON in services/: {json_path}")
        return {
            "file": pdf_file,
            "status": "SUCCESS" if "error" not in result else "FAILED",
            "json": str(json_path),
            "validation": validation,
        }
    except Exception as e:
        print(f"❌ Error while parsing: {e}")
        traceback.print_exc()
        return {"file": pdf_file, "status": "FAILED", "error": str(e), "json": None, "validation": None}

def main() -> None:
    print("=" * 100)
    print("🧪 CREDIT CARD STATEMENT PARSER — TEST SUITE (SBI/HDFC)")
    print("=" * 100)
    parser = UniversalCreditCardParser()
    issuers = parser.get_supported_issuers()
    print(f"✅ Supported issuers: {', '.join(issuers) if issuers else '(none)'}")

    tests: list[tuple[str, str | None]] = [
        # If you keep PDFs alongside test.py:
        (str(CUR_DIR / "CardStatement_2024-07-03 (1).pdf"), "SBI"),
        (str(CUR_DIR / "CardStatement_2025-10-03.pdf"), "SBI"),
        (str(CUR_DIR / "hdfc_statement.pdf"), "HDFC"),
    ]

    # Also scan services/ for any PDFs
    for p in CUR_DIR.glob("*.pdf"):
        if not any(str(p) == t[0] for t in tests):
            tests.append((str(p), None))

    # If you're running in an environment where your samples are at /mnt/data
    mnt = Path("/mnt/data")
    if mnt.exists():
        for p in mnt.glob("*.pdf"):
            if not any(str(p) == t[0] for t in tests):
                tests.append((str(p), None))

    results = [test_single_file(parser, pdf, issuer) for pdf, issuer in tests]

    print("\n" + "=" * 100)
    print("📊 TEST SUITE SUMMARY")
    print("=" * 100)
    succ = sum(1 for r in results if r.get("status") == "SUCCESS")
    fail = sum(1 for r in results if r.get("status") == "FAILED")
    skip = sum(1 for r in results if r.get("status") == "SKIPPED")
    valid_ok = [r["validation"] for r in results if r.get("validation") and r["validation"].get("success")]
    avg_rate = (sum(v["percentage"] for v in valid_ok) / len(valid_ok)) if valid_ok else 0.0
    total_txn = sum(v["transaction_count"] for v in valid_ok) if valid_ok else 0
    print(f"Total Files: {len(results)}")
    print(f"✅ Success: {succ}")
    print(f"❌ Failed:  {fail}")
    print(f"⏭️  Skipped: {skip}")
    print(f"💳 Total Transactions Parsed: {total_txn}")
    print(f"📈 Avg Extraction Rate: {avg_rate:.1f}%")
    print("=" * 100 + "\n")

if __name__ == "__main__":
    main()
