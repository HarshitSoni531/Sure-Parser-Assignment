# services/extractors/hdfc_parser.py
"""
HDFC Credit Card Statement Parser
Extracts key information from HDFC credit card statements with high accuracy.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import pdfplumber


class HDFCParser:
    """Parser for HDFC Credit Card statements"""

    ISSUER = "HDFC"

    # ---- compile once for speed/accuracy ------------------------------------
    _RE_WS = re.compile(r"\s+")
    _RE_AMOUNT = re.compile(r"([\d,]+(?:\.\d{1,2})?)")

    # Common label & number patterns
    _RE_CARD_LABELS = [
        re.compile(r"\bcard\s*(?:no|number)\b", re.I),
        re.compile(r"\bhdfc\s*bank\s*credit\s*card\b", re.I),
    ]

    # e.g., "Card No: 4695 25XX XXXX 3458"  -> tail "3458"
    # or     "Card No: 4695 25XX XXXX XX58" -> tail "XX58"
    _RE_MASK_TAIL = re.compile(
        r"(?:\d{4}[\s\-]*)?(?:\d{2})?(?:X{2,4}|x{2,4})(?:[\s\-]*X{3,4}){0,2}[\s\-]*(\d{2,4})\b"
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
            r"Statement\s+from[:\s]+(\d{1,2}\s+\w+\s+\d{2,4})\s+to\s+(\d{1,2}\s+\w+\s+\d{2,4})",
            re.IGNORECASE,
        ),
    ]

    _RE_STATEMENT_DATE = re.compile(r"Statement\s+Date[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.I)

    # Strict date tokens used for Due Date
    _RE_DATE_TOKEN = re.compile(
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3}(?:\s+\d{2,4})?)\b"
    )

    # direct due-date forms (date on same line)
    _RE_DUE_DATES = [
        re.compile(r"(?:Payment\s+)?Due\s+(?:Date|By)[:\s]+(\d{1,2}[/-]\w{3}[/-]\d{2,4})", re.IGNORECASE),
        re.compile(r"(?:Payment\s+)?Due\s+(?:Date|By)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", re.IGNORECASE),
        re.compile(r"(?:Payment\s+)?Due\s+on[:\s]+(\d{1,2}\s+\w+\s+\d{2,4})", re.IGNORECASE),
    ]

    _RE_TOTAL_DUE = [
        re.compile(r"Total\s+Amount\s+Due[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
        re.compile(r"Total\s+Dues?[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
        re.compile(r"Amount\s+Payable[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
        re.compile(r"Total\s+Outstanding[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE),
    ]

    _RE_VARIANT = [
        # "Paytm HDFC Bank Credit Card"
        re.compile(r"([A-Za-z][A-Za-z \-]+?)\s+HDFC\s+Bank\s+Credit\s+Card", re.I),
        # Explicit "Card Type/Name"
        re.compile(r"(?:Card\s*(?:Type|Name))[:\s]+([A-Z][A-Z \-]+)", re.IGNORECASE),
        # Common HDFC variants
        re.compile(
            r"(REGALIA|DINERS(?:\s+CLUB)?|MILLENNIA|INFINIA|MONEYBACK|FREEDOM|TIMES|PLATINUM|TITANIUM|OCTANE|PAYTM)",
            re.IGNORECASE,
        ),
    ]

    # Labels for label→value-on-next-line extraction
    _LABELS_PAYMENT_DUE_STRICT = [re.compile(r"\bpayment\s+due\s+date\b", re.I)]
    _LABELS_PAYMENT_DUE_LOOSE = [re.compile(r"\bdue\s+date\b", re.I)]
    _LABELS_TOTAL_DUE = [
        re.compile(r"total\s+amount\s+due", re.I),
        re.compile(r"total\s+dues?", re.I),
        re.compile(r"(?:amount|amt)\s+payable", re.I),
        re.compile(r"total\s+outstanding", re.I),
    ]
    _LABELS_CARD_NUMBER = [
        re.compile(r"card\s*no\.?", re.I),
        re.compile(r"card\s*number", re.I),
    ]

    # Lines to ignore if they leak into transactions (headers, summaries)
    _SKIP_TXN_DESC = re.compile(
        r"(reward\s+points|account\s+summary|available\s+(?:credit|cash)\s+limit|past\s+dues|important\s+information|total\s+)\b",
        re.I,
    )
    _SKIP_TOTAL_ROW = re.compile(
        r"^\s*(opening|closing|total|new\s+balance|previous\s+balance|minimum\s+amount\s+due|gst|tax)\b",
        re.I,
    )

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
        "%d/%m",
    )

    def __init__(self) -> None:
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
        Main parsing function for HDFC statements.
        Returns a normalized dict.
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

                header_text = first_two_text or (full_text[0] if full_text else "")

                # Header fields
                result["card_variant"] = self._extract_card_variant(header_text)
                result["card_last_4_digits"] = self._extract_card_number(header_text)

                billing_tuple = self._extract_billing_cycle(header_text)
                statement_date = self._extract_statement_date(header_text)
                if billing_tuple:
                    start, end = billing_tuple
                    result["billing_cycle"] = f"{start} to {end}"

                result["payment_due_date"] = self._extract_due_date(header_text)
                result["total_amount_due"] = self._extract_total_due(header_text)

                # Transactions
                txns = self._extract_transactions_tables(pdf)
                if not txns:
                    txns = self._extract_transactions_regex("\n".join(full_text))

                # Sanity: restrict transactions to billing cycle ±5 days if we have it
                txns = self._filter_txns_to_cycle(txns, billing_tuple, pad_days=5)
                txns = self._dedupe_txns(txns)

                # If no explicit billing cycle but we have statement date + txns, infer from min txn date
                if not result["billing_cycle"] and statement_date and txns:
                    try:
                        end_dt = datetime.strptime(statement_date, "%d-%m-%Y")
                        start_dt = min(datetime.strptime(t["date"], "%d-%m-%Y") for t in txns)
                        if start_dt <= end_dt:
                            result["billing_cycle"] = f"{start_dt.strftime('%d-%m-%Y')} to {end_dt.strftime('%d-%m-%Y')}"
                    except Exception:
                        pass

                result["transactions"] = txns[:100]

        except Exception as e:
            result["error"] = f"HDFC parsing error: {str(e)}"

        return result

    # ========================= FIELD EXTRACTORS ===============================

    def _extract_card_variant(self, text: str) -> Optional[str]:
        for pat in self._RE_VARIANT:
            m = pat.search(text)
            if m:
                var = self._clean(m.group(1))
                var = re.sub(r"\b(CREDIT\s*CARD|CARD)\b", "", var, flags=re.IGNORECASE).strip()
                if var:
                    var = " ".join(w.capitalize() for w in self._RE_WS.split(var) if w)
                    return f"HDFC {var}"
        if re.search(r"\bHDFC\s+Bank\b", text, re.IGNORECASE):
            return "HDFC Credit Card"
        return None

    def _extract_card_number(self, text: str) -> Optional[str]:
        masked_tail = self._value_after_labels(text, self._RE_CARD_LABELS, self._RE_MASK_TAIL, lookahead_lines=4)
        if masked_tail:
            tail = masked_tail.strip()
            if len(tail) == 4:
                return tail
            if len(tail) == 2:
                return f"XX{tail}"

        for line in text.splitlines():
            line = line.strip()
            m = self._RE_MASK_TAIL.search(line)
            if m:
                tail = m.group(1)
                return tail if len(tail) == 4 else f"XX{tail}"

        m = re.search(r"(?:X|\*){4}(?:[\s\-]+(?:X|\*){4}){2}[\s\-]+(\d{2,4})\b", text)
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
        return None

    def _extract_statement_date(self, text: str) -> Optional[str]:
        m = self._RE_STATEMENT_DATE.search(text)
        if m:
            return self._normalize_date(m.group(1))
        return None

    def _extract_due_date(self, text: str) -> Optional[str]:
        """
        Return only a true date-looking token close to the 'Payment Due Date' label.
        Prevents accidental captures like '0 GST'.
        """
        # 1) direct patterns with strict validation
        for pat in self._RE_DUE_DATES:
            m = pat.search(text)
            if m:
                token = m.group(1).strip()
                if self._looks_like_date_token(token):
                    return self._normalize_date(token)

        # helper to scan line windows around labels
        def scan_lines(label_patterns: List[re.Pattern]) -> Optional[str]:
            lines = [self._clean(l) for l in (text or "").splitlines() if self._clean(l)]
            for i, line in enumerate(lines):
                if any(lr.search(line) for lr in label_patterns):
                    for j in range(0, 4):  # this line + next 3
                        if i + j >= len(lines):
                            break
                        m2 = self._RE_DATE_TOKEN.search(lines[i + j])
                        if m2:
                            token = m2.group(1).strip()
                            if self._looks_like_date_token(token):
                                return self._normalize_date(token)
            return None

        # 2) prefer exact 'Payment Due Date'
        got = scan_lines(self._LABELS_PAYMENT_DUE_STRICT)
        if got:
            return got
        # 3) then loose 'Due Date' (can appear in notes)
        got = scan_lines(self._LABELS_PAYMENT_DUE_LOOSE)
        if got:
            return got

        # 4) final fallback: character window after the first strict label occurrence
        text_low = text.lower()
        m = re.search(r"payment\s+due\s+date", text_low)
        if m:
            start = m.end()
            window = text[start : start + 200]
            m2 = self._RE_DATE_TOKEN.search(window)
            if m2:
                token = m2.group(1).strip()
                if self._looks_like_date_token(token):
                    return self._normalize_date(token)

        return None

    def _extract_total_due(self, text: str) -> Optional[str]:
        for pat in self._RE_TOTAL_DUE:
            m = pat.search(text)
            if m:
                return f"₹{m.group(1).replace(',', '')}"
        amt_re = re.compile(r"(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)", re.I)
        raw = self._value_after_labels(text, self._LABELS_TOTAL_DUE, amt_re, lookahead_lines=4)
        if raw:
            return f"₹{raw.replace(',', '')}"
        return None

    # ======================= TRANSACTION EXTRACTORS ===========================

    def _extract_transactions_tables(self, pdf) -> List[Dict[str, Any]]:
        txns: List[Dict[str, Any]] = []
        for page in pdf.pages:
            try:
                tables = page.extract_tables()
            except Exception:
                tables = []
            for table in tables or []:
                if not table or len(table) < 2:
                    continue
                norm_rows = [[self._clean(c) for c in (row or [])] for row in table]
                header_idx, header = self._find_header(norm_rows)
                if header_idx is None:
                    continue
                colmap = self._map_columns(header)
                if colmap.get("date") is None:
                    continue
                for row in norm_rows[header_idx + 1 :]:
                    if len(row) < len(header):
                        row = row + [""] * (len(header) - len(row))
                    date_cell = row[colmap["date"]] if colmap.get("date") is not None else ""
                    if not self._looks_like_date(date_cell):
                        continue
                    # description
                    desc_parts: List[str] = []
                    for k in ("desc", "desc2", "merchant", "remarks"):
                        idx = colmap.get(k)
                        if idx is not None and idx < len(row):
                            desc_parts.append(row[idx])
                    desc_clean = self._strip_amount_trail(self._clean(" ".join(p for p in desc_parts if p)))
                    if not desc_clean or self._SKIP_TXN_DESC.search(desc_clean) or self._SKIP_TOTAL_ROW.search(desc_clean):
                        continue
                    # amount
                    sign = "-"
                    amount_str = ""
                    if colmap.get("amount") is not None:
                        amount_str = row[colmap["amount"]]
                        tail = " ".join([amount_str, row[colmap["crdr"]] if colmap.get("crdr") is not None else ""])
                        if re.search(r"\bcr\b", tail, re.I):
                            sign = "+"
                    else:
                        debit_val = row[colmap["debit"]] if colmap.get("debit") is not None else ""
                        credit_val = row[colmap["credit"]] if colmap.get("credit") is not None else ""
                        if self._RE_AMOUNT.search(credit_val):
                            amount_str = credit_val
                            sign = "+"
                        elif self._RE_AMOUNT.search(debit_val):
                            amount_str = debit_val
                            sign = "-"
                    amt = self._extract_amount(amount_str)
                    if amt is None:
                        continue
                    txns.append(
                        {
                            "date": self._normalize_date_flex(date_cell),
                            "description": desc_clean,
                            "amount": f"{sign}₹{amt}",
                        }
                    )
        return txns

    def _extract_transactions_regex(self, text: str) -> List[Dict[str, Any]]:
        txns: List[Dict[str, Any]] = []
        pattern = re.compile(
            r"(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4})"
            r"\s+(?P<desc>.+?)\s+(?:Rs\.?|INR|₹)?\s*(?P<amt>[\d,]+(?:\.\d{1,2})?)\s*(?P<crdr>Cr|DR|CR)?\b",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            raw_date = m.group("date")
            desc = self._strip_amount_trail(m.group("desc"))
            amt = m.group("amt")
            crdr = (m.group("crdr") or "").lower()
            if not desc or len(desc) < 3:
                continue
            if self._SKIP_TXN_DESC.search(desc) or self._SKIP_TOTAL_ROW.search(desc):
                continue
            sign = "+" if "cr" in crdr else "-"
            amt_norm = amt.replace(",", "")
            txns.append(
                {"date": self._normalize_date_flex(raw_date), "description": desc, "amount": f"{sign}₹{amt_norm}"}
            )
        return txns

    # ============================= HELPERS ====================================

    def _value_after_labels(
        self, text: str, label_res: List[re.Pattern], value_res: re.Pattern, lookahead_lines: int = 2
    ) -> Optional[str]:
        lines = [self._clean(l) for l in (text or "").splitlines() if self._clean(l)]
        for idx, line in enumerate(lines):
            for lr in label_res:
                if lr.search(line):
                    m = value_res.search(line)
                    if m:
                        return m.group(1)
                    for j in range(1, lookahead_lines + 1):
                        if idx + j < len(lines):
                            mm = value_res.search(lines[idx + j])
                            if mm:
                                return mm.group(1)
        return None

    def _filter_txns_to_cycle(
        self, txns: List[Dict[str, Any]], cycle: Optional[Tuple[str, str]], pad_days: int = 0
    ) -> List[Dict[str, Any]]:
        if not cycle or not txns:
            return txns
        try:
            start = datetime.strptime(cycle[0], "%d-%m-%Y") - timedelta(days=pad_days)
            end = datetime.strptime(cycle[1], "%d-%m-%Y") + timedelta(days=pad_days)
        except Exception:
            return txns
        kept: List[Dict[str, Any]] = []
        for t in txns:
            try:
                dt = datetime.strptime(t["date"], "%d-%m-%Y")
                if start <= dt <= end and t.get("description"):
                    kept.append(t)
            except Exception:
                kept.append(t)
        return kept

    def _dedupe_txns(self, txns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out: List[Dict[str, Any]] = []
        for t in txns:
            key = (t.get("date"), t.get("description"), t.get("amount"))
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out

    def _find_header(self, rows: List[List[str]]) -> Tuple[Optional[int], Optional[List[str]]]:
        candidates = ("date", "transaction", "description", "amount", "debit", "credit", "cr/dr", "remarks", "merchant")
        for idx, row in enumerate(rows[:6]):
            joined = " ".join((row or []))
            lower = joined.lower()
            score = sum(1 for w in candidates if w in lower)
            if score >= 2:
                return idx, row
        return None, None

    def _map_columns(self, header: List[str]) -> Dict[str, Optional[int]]:
        cols = {
            "date": None,
            "desc": None,
            "desc2": None,
            "merchant": None,
            "remarks": None,
            "amount": None,
            "debit": None,
            "credit": None,
            "crdr": None,
        }
        for i, h in enumerate(header):
            hl = (h or "").strip().lower()
            if "date" in hl and cols["date"] is None:
                cols["date"] = i
            elif any(k in hl for k in ("desc", "narration", "transaction", "particular", "merchant")):
                if cols["desc"] is None:
                    cols["desc"] = i
                elif cols["desc2"] is None:
                    cols["desc2"] = i
            elif "remarks" in hl and cols["remarks"] is None:
                cols["remarks"] = i
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
        if re.match(r"\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?$", s):
            return True
        if re.match(r"\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4}$", s):
            return True
        return False

    def _looks_like_date_token(self, s: str) -> bool:
        s = (s or "").strip()
        if re.fullmatch(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", s):
            return True
        if re.fullmatch(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}", s):
            return True
        if re.fullmatch(r"\d{1,2}\s+[A-Za-z]{3}", s):
            return True
        return False

    def _normalize_date_flex(self, raw: str) -> str:
        raw = (raw or "").strip()
        return self._normalize_date(raw)

    def _normalize_date(self, date_str: str) -> str:
        s = (date_str or "").strip()
        for fmt in self._DATE_FORMATS:
            try:
                dt = datetime.strptime(s, fmt)
                if dt.year < 1970:
                    dt = dt.replace(year=datetime.now().year)
                return dt.strftime("%d-%m-%Y")
            except ValueError:
                continue
        return s

    def _strip_amount_trail(self, text: str) -> str:
        if not text:
            return ""
        t = self._RE_WS.sub(" ", str(text)).strip()
        t = re.sub(r"\s+(?:Rs\.?|INR|₹)?\s*[\d,]+(?:\.\d{1,2})?\s*(?:Cr|DR|CR)?\s*$", "", t, flags=re.IGNORECASE)
        return t

    def _clean(self, text: Optional[str]) -> str:
        if not text:
            return ""
        return self._RE_WS.sub(" ", str(text)).strip()
