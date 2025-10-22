#!/usr/bin/env python3
"""
Universal Credit Card Statement Parser (SBI + HDFC only)

- Loads only ./extractors/sbi_parser.py and ./extractors/hdfc_parser.py
- Auto-identifies issuer from the first 1–2 PDF pages
- Falls back to trying both parsers and picks the best by field coverage
- Normalizes output across issuers
- NEW: optional --save and --outdir (defaults to services/) to write JSON
"""

from __future__ import annotations

import os
import re
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import importlib.util

# Optional: used only for auto-identification
try:
    import pdfplumber  # type: ignore
except Exception:
    pdfplumber = None

ALLOWED_FILES = {"sbi_parser.py", "hdfc_parser.py"}
ALLOWED_ISSUERS = {"SBI", "HDFC"}


class UniversalCreditCardParser:
    def __init__(self) -> None:
        self.parsers: Dict[str, Any] = {}
        self._load_parsers()

    def _load_parsers(self) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        extractors_path = os.path.join(base_dir, "extractors")

        if not os.path.isdir(extractors_path):
            print(f"⚠️  extractors directory not found: {extractors_path}")
            return

        for filename in os.listdir(extractors_path):
            if filename not in ALLOWED_FILES:
                continue
            module_path = os.path.join(extractors_path, filename)
            try:
                spec = importlib.util.spec_from_file_location(filename, module_path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)  # type: ignore

                    parser_cls = None
                    for attr_name in dir(mod):
                        if attr_name.endswith("Parser"):
                            cls = getattr(mod, attr_name)
                            if isinstance(cls, type):
                                parser_cls = cls
                                break
                    if parser_cls is None:
                        print(f"⚠️  No Parser class found in {filename}")
                        continue

                    parser_instance = parser_cls()
                    issuer_name = getattr(parser_instance, "ISSUER", filename.replace("_parser.py", "").upper())
                    issuer_name = str(issuer_name).upper()

                    if issuer_name in ALLOWED_ISSUERS:
                        self.parsers[issuer_name] = parser_instance
                        print(f"✅ Loaded parser: {issuer_name}")
                    else:
                        print(f"⚠️  Ignored parser {issuer_name} (not in allowed list)")
                else:
                    print(f"⚠️  Could not load module from {module_path}")
            except Exception as e:
                print(f"❌ Error loading {filename}: {e}")

    def identify_issuer(self, pdf_path: str) -> Optional[str]:
        if pdfplumber is None:
            return None
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages[:2]:
                    text += page.extract_text() or ""
        except Exception:
            return None

        t = text.lower()
        signatures: List[Tuple[str, List[str]]] = [
            ("SBI", ["sbi card", "state bank of india"]),
            ("HDFC", ["hdfc bank", "hdfc credit card"]),
        ]
        for issuer, needles in signatures:
            if any(n in t for n in needles):
                return issuer
        return None

    def parse(self, pdf_path: str, issuer: Optional[str] = None) -> Dict[str, Any]:
        if not os.path.exists(pdf_path):
            return {"error": f"File not found: {pdf_path}"}

        issuer_key = (issuer or "").upper() if issuer else self.identify_issuer(pdf_path)
        if issuer_key and issuer_key in self.parsers:
            try:
                res = self.parsers[issuer_key].parse(pdf_path)
                res["issuer"] = issuer_key
                res["parsed_at"] = datetime.now().isoformat()
                return res
            except Exception as e:
                return {
                    "error": f"Parsing failed for {issuer_key}: {e}",
                    "issuer": issuer_key,
                    "parsed_at": datetime.now().isoformat(),
                }

        # Fallback: try both and pick best
        best_res: Optional[Dict[str, Any]] = None
        best_score = -1.0
        best_issuer: Optional[str] = None
        for name, parser in self.parsers.items():
            try:
                r = parser.parse(pdf_path)
                score = self._score_result(r, getattr(parser, "required_fields", []))
                if score > best_score:
                    best_score = score
                    best_res = r
                    best_issuer = name
            except Exception:
                continue

        if best_res is not None:
            best_res["issuer"] = best_issuer
            best_res["parsed_at"] = datetime.now().isoformat()
            return best_res

        return {
            "error": "Could not identify issuer or parse with available parsers (SBI/HDFC).",
            "parsed_at": datetime.now().isoformat(),
        }

    def get_supported_issuers(self) -> List[str]:
        return sorted(self.parsers.keys())

    def _score_result(self, result: Dict[str, Any], required_fields: List[str]) -> float:
        if not result or "error" in result:
            return 0.0
        score = 0.0
        for f in required_fields or []:
            if result.get(f):
                score += 1.0
        txns = result.get("transactions")
        if isinstance(txns, list) and txns:
            score += 0.2
        return score


def _save_result_json(result: Dict[str, Any], pdf_path: str, outdir: Optional[str]) -> str:
    """
    Save parsed result to JSON.
    Default outdir is the 'services' directory (same folder as this file).
    """
    base_services_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = outdir or base_services_dir

    os.makedirs(out_dir, exist_ok=True)

    issuer = (result.get("issuer") or "unknown").lower()
    last4 = result.get("card_last_4_digits") or "xxxx"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    fname = f"{issuer}_{last4}_{base}_{ts}.json"
    out_path = os.path.join(out_dir, fname)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    return out_path


def format_output(data: Dict[str, Any], format_type: str = "pretty") -> str:
    if format_type == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    if format_type == "csv":
        import csv
        import io
        flat = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in data.items()}
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=list(flat.keys()))
        writer.writeheader()
        writer.writerow(flat)
        return buf.getvalue()

    lines: List[str] = []
    sep = "=" * 70
    lines.append(sep)
    lines.append("CREDIT CARD STATEMENT PARSER - RESULTS")
    lines.append(sep)

    if "error" in data:
        lines.append(f"\n❌ ERROR: {data.get('error')}\n")
        return "\n".join(lines)

    show = [
        ("Issuer", data.get("issuer")),
        ("Parsed At", data.get("parsed_at")),
        ("Card Variant", data.get("card_variant")),
        ("Card Last 4", data.get("card_last_4_digits")),
        ("Billing Cycle", data.get("billing_cycle")),
        ("Payment Due Date", data.get("payment_due_date")),
        ("Total Amount Due", data.get("total_amount_due")),
    ]
    for label, val in show:
        if val:
            lines.append(f"📌 {label}: {val}")

    txns = data.get("transactions") or []
    lines.append(f"\n📋 Transactions: {len(txns)} found")
    if txns:
        lines.append("   Recent:")
        for i, t in enumerate(txns[:5], 1):
            if isinstance(t, dict):
                d = t.get("date", "N/A")
                desc = str(t.get("description", "N/A"))
                if len(desc) > 50:
                    desc = desc[:47] + "..."
                amt = t.get("amount", "N/A")
                lines.append(f"   {i}. {d} | {desc} | {amt}")
            else:
                s = str(t)
                if len(s) > 70:
                    s = s[:67] + "..."
                lines.append(f"   {i}. {s}")

        if len(txns) > 5:
            lines.append(f"   ... and {len(txns) - 5} more")

    lines.append("\n" + sep)
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Universal Credit Card Statement Parser (SBI/HDFC)")
    ap.add_argument("pdf", help="Path to statement PDF")
    ap.add_argument("--issuer", help="Issuer override: SBI or HDFC", default=None)
    ap.add_argument("--format", help="Output format: pretty|json|csv", default="pretty")
    ap.add_argument("--save", help="Save JSON output", action="store_true")
    ap.add_argument(
        "--outdir",
        help="Directory to save JSON (default: services/)",
        default=None
    )
    args = ap.parse_args()

    parser = UniversalCreditCardParser()
    print(f"✅ Supported issuers: {', '.join(parser.get_supported_issuers()) or '(none)'}\n")

    res = parser.parse(args.pdf, issuer=args.issuer)
    print(format_output(res, args.format))

    if args.save and "error" not in res:
        saved = _save_result_json(res, args.pdf, args.outdir)
        print(f"\n💾 Saved JSON: {saved}")
