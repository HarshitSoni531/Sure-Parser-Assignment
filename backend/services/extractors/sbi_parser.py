# services/extractors/sbi_parser.py
"""
SBI Credit Card Statement Parser
Extracts key information from SBI credit card statements with high accuracy.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import pdfplumber


class SBIParser:
    """Parser for SBI Credit Card statements"""

    # ---- compile once for speed/accuracy ------------------------------------
    _RE_WS = re.compile(r"\s+")
    _RE_AMOUNT = re.compile(r"([\d,]+(?:\.\d{1,2})?)")

    # classic "…1234" patterns
    _RE_MASKED_LAST4 = re.compile(
        r"(?:Card\s*(?:Number|No\.?)|Credit\s*Card\s*(?:Number|No\.?)|Card\s*Ending|Card\s*Ending\s*with)"
        r"[:\s]*[Xx*]+[ \-Xx*]*[Xx*]+[ \-Xx*]*[Xx*]+[ \-Xx*]*(\d{4})"
    )
    _RE_LAST4_FALLBACK = re.compile(
        r"(?:XXXX|xxxx|\*{4})[ -]*(?:XXXX|xxxx|\*{4})[ -]*(?:XXXX|xxxx|\*{4})[ -]*(\d{4})"
    )

    _RE_PERIODS = [
        re.compile(
            r"(?:Statement|Billing)\s+(?:Period|Cycle|Date)[:\s]+"
            r"(\d{1,2}[/-]\w{3}[/-]\d{2,4})\s+(?:to|-)\s+(\d{1,2}[/-]\w{3}[/-]\d{2,4})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:Statement|Billing)\s+(?:Period|Cycle|Date)[:\s]+"
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?:to|-)\s+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            re.IGNORECASE,
        ),
        re.compile(
            r"Period\s*(?:From)?[:\s]+(\d{1,2}\s+\w+\s+\d{2,4})\s+(?:to|-)\s+(\d{1,2}\s+\w+\s+\d{2,4})",
            re.IGNORECASE,
        ),
    ]

    _RE_DUE_DATES = [
        re.compile(r"(?:Payment\s+)?Due\s+(?:Date|By)[:\s]+(\d{1,2}[/-]\w{3}[/-]\d{2,4})", re.IGNORECASE),
        re.compile(r"(?:Payment\s+)?Due\s+(?:Date|By)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE),
        re.compile(r"(?:Payment\s+)?Due\s+on[:\s]+(\d{1,2}\s+\w+\s+\d{2,4})", re.IGNORECASE),
        re.compile(r"Last\s+Date\s+for\s+Payment[:\s]+(\d{1,2}[/-]\w{3}[/-]\d{2,4})", re.IGNORECASE),
    ]

    _RE_TOTAL_DUE = [
        re.compile(r"Total\s+Amount\s+Due[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
        re.compile(r"Total\s+(?:Outstanding|Dues?)[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
        re.compile(r"Closing\s+Balance[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    ]

    _RE_VARIANT = [
        # Explicit "Card Type/Name"
        re.compile(r"(?:Card\s*(?:Type|Name))[:\s]+([A-Z][A-Z \-]+)", re.IGNORECASE),
        # “Your SBI Card SIMPLYCLICK …”
        re.compile(r"Your\s+SBI\s+Card\s+([A-Z][A-Z \-]+)", re.IGNORECASE),
        # Common SBI variants
        re.compile(
            r"(AURUM|ELITE|PRIME|SIMPLYCLICK|SIMPLYSAVE|BPCL|OLA|IRCTC|AIR\s*INDIA|CLUB\s*VISTARA|YATRA|OCTANE)",
            re.IGNORECASE,
        ),
    ]

    # Labels for label→value-on-next-line extraction
    _LABELS_PAYMENT_DUE = [re.compile(r"payment\s+due\s+date", re.I), re.compile(r"\bdue\s+date\b", re.I)]
    _LABELS_TOTAL_DUE = [
        re.compile(r"total\s+amount\s+due", re.I),
        re.compile(r"total\s+dues?", re.I),
        re.compile(r"(?:amount|amt)\s+payable", re.I),
    ]
    _LABELS_CARD_NUMBER = [
        re.compile(r"credit\s*card\s*number", re.I),
        re.compile(r"card\s*(?:a/c|ac|account)?\s*(?:no|number)", re.I),
    ]

    # Lines to ignore if they leak into transactions
    _SKIP_TXN_DESC = re.compile(r"(available\s+(?:credit|cash)\s+limit|payment\s+due\s+date)", re.I)

    _DATE_FORMATS = (
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d-%b-%Y",
        "%d/%b/%Y",
        "%d-%m-%y",
        "%d/%m/%y",
        "%d-%b-%y",
        "%d/%b/%y",
        "%d %B %Y",
        "%d %b %Y",
        "%d-%m",
        "%d/%m",  # sometimes transactions omit the year
    )

    def __init__(self) -> None:
        # For parity with your HDFC parser/tests
        self.required_fields = [
            "card_variant",
            "card_last_4_digits",
            "billing_cycle",
            "payment_due_date",
            "total_amount_due",
        ]

    # -------------------------------------------------------------------------
    def parse(self, pdf_path: str) -> Dict[str, Any]:
        """
        Main parsing function for SBI statements.
        Returns a normalized dict similar to HDFCParser's output.
        """
        result: Dict[str, Any] = {
            "card_variant": None,
            "card_last_4_digits": None,
            "billing_cycle": None,
            "payment_due_date": None,
            "total_amount_due": None,
            "transactions": [],
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_two_text = ""
                full_text = []

                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text() or ""
                    full_text.append(text)
                    if page_num <= 2:
                        first_two_text += text + "\n"

                # ---- Header fields from first page(s) ------------------------
                page1_text = full_text[0] if full_text else ""
                header_text = first_two_text or page1_text

                result["card_variant"] = self._extract_card_variant(header_text)
                result["card_last_4_digits"] = self._extract_card_number(header_text)

                billing_tuple = self._extract_billing_cycle(header_text)
                if billing_tuple:
                    start, end = billing_tuple
                    result["billing_cycle"] = f"{start} to {end}"

                # Context year for txn dates that omit year (use end of cycle)
                context_year: Optional[int] = None
                if billing_tuple:
                    try:
                        context_year = datetime.strptime(billing_tuple[1], "%d-%m-%Y").year
                    except Exception:
                        context_year = None

                result["payment_due_date"] = self._extract_due_date(header_text, context_year=context_year)
                result["total_amount_due"] = self._extract_total_due(header_text)

                # ---- Transactions: prefer table extraction, fallback to regex -
                txns = self._extract_transactions_tables(pdf, context_year=context_year)
                if not txns:
                    txns = self._extract_transactions_regex("\n".join(full_text), context_year=context_year)

                # Keep top 100
                result["transactions"] = txns[:100]

        except Exception as e:
            result["error"] = f"SBI parsing error: {str(e)}"

        return result

    # ========================= FIELD EXTRACTORS ===============================

    def _extract_card_variant(self, text: str) -> Optional[str]:
        for pat in self._RE_VARIANT:
            m = pat.search(text)
            if m:
                var = self._clean(m.group(1))
                # Remove generic trailing words if present
                var = re.sub(r"\b(CREDIT\s*CARD|CARD)\b", "", var, flags=re.IGNORECASE).strip()
                if var:
                    # Normalize spacing & casing
                    var = self._RE_WS.sub(" ", var).upper()
                    return f"SBI {var}"
        # Fallback: if SBI detected but no variant, still say "SBI Card"
        if re.search(r"\bSBI\s+Card\b|\bState\s+Bank\s+of\s+India\b", text, re.IGNORECASE):
            return "SBI Card"
        return None

    def _extract_card_number(self, text: str) -> Optional[str]:
        """
        Extract last visible digits. SBI sometimes shows:
          - XXXX XXXX XXXX 1234        (4 visible)
          - XXXX XXXX XXXX XX92        (only last 2 visible)
          - XXXXXXXXXXXX 1234          (single block mask)
        We return:
          - '1234' when 4 digits visible
          - 'XX92' when only 2 visible (so the UI shows **** **** **** XX92)
        """
        # 1) Typical labeled formats (…1234)
        m = self._RE_MASKED_LAST4.search(text)
        if m:
            return m.group(1)

        # 2) Common XXXX-XXXX-XXXX-1234 or XXXX XXXX XXXX 1234
        m = self._RE_LAST4_FALLBACK.search(text)
        if m:
            return m.group(1)

        # 3) Label→value on next line, e.g.:
        #    "Credit Card Number"
        #    "XXXX XXXX XXXX XX92"
        masked_tail_re = re.compile(r"(?:(?:X|\*)[\s\-]*)+(?P<tail>\d{2,4})\b", re.I)
        raw = self._value_after_labels(text, self._LABELS_CARD_NUMBER, masked_tail_re, lookahead_lines=3)
        if raw:
            tail = raw.strip()
            if len(tail) == 4:
                return tail
            if len(tail) == 2:
                # explicitly convey the mask for the two missing digits
                return f"XX{tail}"

        # 4) One-block masking then tail digits (XXXXXXXXXXXX 1234)
        m = re.search(r"(?:X|\*){8,}[\s\-]*(?:X|\*)*[\s\-]*(\d{2,4})\b", text)
        if m:
            tail = m.group(1)
            return tail if len(tail) == 4 else f"XX{tail}"

        # 5) Free-line fallback: scan lines for something like "XXXX XXXX XXXX XX92"
        for line in text.splitlines():
            line = line.strip()
            m = re.search(r"(?:(?:X|\*)[\s\-]*){6,}(\d{2,4})$", line, re.I)
            if m:
                tail = m.group(1)
                return tail if len(tail) == 4 else f"XX{tail}"

        # 6) Label variants like "Card A/c No." with masks
        m = re.search(
            r"(?:card\s*(?:a/c|ac|account)?\s*(?:no|number)\.?)\s*[:\-]?\s*(?:X|\*){4,}[\s\-\*X]*(\d{2,4})",
            text,
            re.I,
        )
        if m:
            tail = m.group(1)
            return tail if len(tail) == 4 else f"XX{tail}"

        return None

    def _extract_billing_cycle(self, text: str) -> Optional[Tuple[str, str]]:
        for pat in self._RE_PERIODS:
            m = pat.search(text)
            if m:
                start = self._normalize_date(m.group(1))
                end = self._normalize_date(m.group(2))
                if start and end:
                    return start, end
        # Some SBI PDFs show "Statement Date:" and "From/To" separately; try heuristic
        from_to = re.search(
            r"(?:From|Period\s*From)[:\s]+([0-9]{1,2}[/-]\w{3}[/-]\d{2,4}|[0-9]{1,2}[/-][0-9]{1,2}[/-]\d{2,4})"
            r"\s+(?:To|to|-)\s+([0-9]{1,2}[/-]\w{3}[/-]\d{2,4}|[0-9]{1,2}[/-][0-9]{1,2}[/-]\d{2,4})",
            text,
            re.IGNORECASE,
        )
        if from_to:
            return self._normalize_date(from_to.group(1)), self._normalize_date(from_to.group(2))
        return None

    def _extract_due_date(self, text: str, context_year: Optional[int] = None) -> Optional[str]:
        # Try existing direct patterns first
        for pat in self._RE_DUE_DATES:
            m = pat.search(text)
            if m:
                return self._normalize_date(m.group(1))

        # Accept dd Mon [yy]? (no year allowed) via label→next-line search
        dd_mon = re.compile(r"(\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{2,4})?)")
        raw = self._value_after_labels(text, self._LABELS_PAYMENT_DUE, dd_mon, lookahead_lines=3)
        if raw:
            # Add context year if missing
            norm = self._normalize_date(self._maybe_add_year(raw, fallback_year=context_year))
            return norm

        # Occasionally shown as "Pay by DD-MMM-YYYY"
        m = re.search(r"Pay\s*by[:\s]+(\d{1,2}\s+\w+\s+\d{2,4})", text, re.IGNORECASE)
        if m:
            return self._normalize_date(m.group(1))

        return None

    def _extract_total_due(self, text: str) -> Optional[str]:
        # Direct patterns
        for pat in self._RE_TOTAL_DUE:
            m = pat.search(text)
            if m:
                return f"₹{m.group(1).replace(',', '')}"

        # Label/next-line search; support commas/decimals and optional currency text
        amt_re = re.compile(r"(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.I)
        raw = self._value_after_labels(text, self._LABELS_TOTAL_DUE, amt_re, lookahead_lines=3)
        if raw:
            return f"₹{raw.replace(',', '')}"

        # Some layouts print "Total Dues (INR)" with amount alone on next line
        raw2 = self._value_after_labels(text, [re.compile(r"total\s+dues?\s*\(.*\)", re.I)], amt_re, lookahead_lines=3)
        if raw2:
            return f"₹{raw2.replace(',', '')}"

        return None

    # ======================= TRANSACTION EXTRACTORS ===========================

    def _extract_transactions_tables(self, pdf, context_year: Optional[int]) -> List[Dict[str, Any]]:
        """
        Parse tables on each page. SBI tables typically have headers like:
        Date | Description | Amount (INR) | (optional) CR/DR or separate Credit/Debit column
        """
        txns: List[Dict[str, Any]] = []

        for page in pdf.pages:
            try:
                tables = page.extract_tables()
            except Exception:
                tables = []

            for table in tables or []:
                if not table or len(table) < 2:
                    continue

                # Normalize rows to strings
                norm_rows = [[self._clean(c) for c in (row or [])] for row in table]

                header_idx, header = self._find_header(norm_rows)
                if header_idx is None:
                    continue

                colmap = self._map_columns(header)
                if not colmap.get("date") or not (colmap.get("amount") or colmap.get("debit") or colmap.get("credit")):
                    # needs at least date and some amount column(s)
                    continue

                for row in norm_rows[header_idx + 1 :]:
                    # Sometimes tables have uneven lengths; pad
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))

                    date_cell = row[colmap["date"]] if colmap.get("date") is not None else ""
                    if not self._looks_like_date(date_cell):
                        # Skip non-transaction lines (subtotals, headers repeated)
                        continue

                    desc_cell = row[colmap["desc"]] if colmap.get("desc") is not None else ""

                    # Determine amount & sign
                    amount_str, sign = None, "-"
                    if colmap.get("amount") is not None:
                        amount_str = row[colmap["amount"]]
                        # Look for CR/DR text in same or a separate column
                        crdr_text = ""
                        if colmap.get("crdr") is not None:
                            crdr_text = row[colmap["crdr"]]
                        if "cr" in (amount_str + " " + crdr_text).lower():
                            sign = "+"
                    else:
                        # Separate credit/debit cols
                        debit_val = row[colmap["debit"]] if colmap.get("debit") is not None else ""
                        credit_val = row[colmap["credit"]] if colmap.get("credit") is not None else ""
                        if self._RE_AMOUNT.search(credit_val or ""):
                            amount_str = credit_val
                            sign = "+"
                        elif self._RE_AMOUNT.search(debit_val or ""):
                            amount_str = debit_val
                            sign = "-"

                    amt = self._extract_amount(amount_str)
                    if amt is None:
                        continue

                    desc_clean = self._strip_amount_trail(desc_cell)
                    if self._SKIP_TXN_DESC.search(desc_clean):
                        continue

                    txns.append(
                        {
                            "date": self._normalize_txn_date(date_cell, context_year=context_year),
                            "description": desc_clean,
                            "amount": f"{sign}₹{amt}",
                        }
                    )

        return txns

    def _extract_transactions_regex(self, text: str, context_year: Optional[int]) -> List[Dict[str, Any]]:
        """
        Regex fallback for transactions when tables aren't extractable.
        Matches lines like:
          DD/MM[/YY]  DESCRIPTION TEXT ....  1,234.56 CR
          DD-MMM-YYYY DESCRIPTION           INR 2,345.00
        """
        txns: List[Dict[str, Any]] = []

        # tolerate multi-space & currency labels; capture CR/DR if present
        pattern = re.compile(
            r"(?P<date>\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4})"
            r"\s+(?P<desc>.+?)\s+(?:Rs\.?|INR|₹)?\s*(?P<amt>[\d,]+(?:\.\d{1,2})?)\s*(?P<crdr>CR|DR)?\b",
            re.IGNORECASE,
        )

        for m in pattern.finditer(text):
            raw_date = m.group("date")
            desc = self._strip_amount_trail(m.group("desc"))
            amt = m.group("amt")
            crdr = (m.group("crdr") or "").lower()

            if not desc or len(desc) < 3:
                continue
            if self._SKIP_TXN_DESC.search(desc):
                continue

            sign = "+" if "cr" in crdr else "-"
            amt_norm = amt.replace(",", "")
            txns.append(
                {
                    "date": self._normalize_txn_date(raw_date, context_year=context_year),
                    "description": desc,
                    "amount": f"{sign}₹{amt_norm}",
                }
            )

        return txns

    # ============================= HELPERS ====================================

    def _value_after_labels(
        self, text: str, label_res: List[re.Pattern], value_res: re.Pattern, lookahead_lines: int = 2
    ) -> Optional[str]:
        """
        When PDFs place labels and values in different columns/lines, find the label
        and look on the same or next N lines for the value.
        Returns group(1) of value_res if matched.
        """
        lines = [self._clean(l) for l in (text or "").splitlines() if self._clean(l)]
        for idx, line in enumerate(lines):
            for lr in label_res:
                if lr.search(line):
                    # same line first
                    m = value_res.search(line)
                    if m:
                        return m.group(1)
                    # then lookahead lines
                    for j in range(1, lookahead_lines + 1):
                        if idx + j < len(lines):
                            mm = value_res.search(lines[idx + j])
                            if mm:
                                return mm.group(1)
        return None

    def _maybe_add_year(self, date_str: str, fallback_year: Optional[int] = None) -> str:
        s = (date_str or "").strip()
        # If it already has a 4-digit or 2-digit year, keep it
        if re.search(r"\b\d{4}\b", s) or re.search(r"\b\d{2}\b", s.split()[-1]):
            return s
        year = fallback_year or datetime.now().year
        return f"{s} {year}"

    def _find_header(self, rows: List[List[str]]) -> Tuple[Optional[int], Optional[List[str]]]:
        """
        Find the most likely header row by looking for expected keywords.
        """
        header_candidates = (
            "date",
            "transaction",
            "description",
            "amount",
            "debit",
            "credit",
            "value",
            "cr/dr",
            "remarks",
        )

        for idx, row in enumerate(rows[:6]):  # headers usually near top of each table
            joined = " ".join((row or []))
            lower = joined.lower()
            score = sum(1 for w in header_candidates if w in lower)
            if score >= 2:
                return idx, row
        return None, None

    def _map_columns(self, header: List[str]) -> Dict[str, Optional[int]]:
        """
        Map header names to indices (date/desc/amount or debit/credit/crdr).
        """
        cols = {"date": None, "desc": None, "amount": None, "debit": None, "credit": None, "crdr": None}
        for i, h in enumerate(header):
            hl = (h or "").strip().lower()
            if "date" in hl and cols["date"] is None:
                cols["date"] = i
            elif any(k in hl for k in ("desc", "narration", "particular", "merchant")) and cols["desc"] is None:
                cols["desc"] = i
            elif "amount" in hl and cols["amount"] is None:
                cols["amount"] = i
            elif "debit" in hl and cols["debit"] is None:
                cols["debit"] = i
            elif "credit" in hl and cols["credit"] is None:
                cols["credit"] = i
            elif "cr/dr" in hl or "crdr" in hl or "cr / dr" in hl:
                cols["crdr"] = i
        return cols

    def _extract_amount(self, s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        m = self._RE_AMOUNT.search(s)
        if not m:
            return None
        return m.group(1).replace(",", "")

    def _looks_like_date(self, s: str) -> bool:
        s = (s or "").strip()
        if not s:
            return False
        # quick pattern checks
        if re.match(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?$", s):
            return True
        if re.match(r"\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4}$", s):
            return True
        return False

    def _normalize_txn_date(self, raw: str, context_year: Optional[int]) -> str:
        """Normalize transaction date to DD-MM-YYYY. If year is missing, use context_year when available."""
        raw = (raw or "").strip()
        # If only dd-mm or dd/mm present, add context year
        if re.match(r"^\d{1,2}[/-]\d{1,2}$", raw) and context_year:
            raw = f"{raw}-{context_year}"
        # Also support 'dd Mon yy' / 'dd Mon' etc.
        if re.match(r"^\d{1,2}\s+[A-Za-z]{3}\s*\d{0,4}$", raw) and context_year and not re.search(r"\d{4}$", raw):
            raw = f"{raw} {context_year}"

        return self._normalize_date(raw)

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date format to DD-MM-YYYY; return original on failure."""
        s = (date_str or "").strip()
        for fmt in self._DATE_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                # If format lacked year (%d-%m), year defaults to 1900; fix by inferring current year if absurd
                if dt.year < 1970:
                    dt = dt.replace(year=datetime.now().year)
                return dt.strftime("%d-%m-%Y")
            except ValueError:
                continue
        return s  # fall back to raw string when unparsable

    def _strip_amount_trail(self, text: str) -> str:
        """
        Clean description: collapse whitespace, strip trailing amounts or CR/DR notes.
        """
        if not text:
            return ""
        t = self._RE_WS.sub(" ", str(text)).strip()
        # remove trailing currency/amount tokens & CR/DR suffixes
        t = re.sub(r"\s+(?:Rs\.?|INR|₹)?\s*[\d,]+(?:\.\d{1,2})?\s*(?:CR|DR)?\s*$", "", t, flags=re.IGNORECASE)
        return t

    def _clean(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return self._RE_WS.sub(" ", str(text)).strip()
