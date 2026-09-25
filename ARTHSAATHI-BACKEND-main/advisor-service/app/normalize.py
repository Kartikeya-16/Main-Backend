import re
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Tuple, Any
from app.schemas import ParsedTxn

# Keywords indicating non-transaction rows to skip
SKIP_ROW_KEYWORDS = [
    "brought forward",
    "opening balance",
    "b/f",
    "closing balance",
    "total",
    "grand total",
    "page",
    "statement of account",
    "account statement",
    "balance brought forward",
    "c/f",
    "carried forward",
    "transaction date",
    "date",
    "narration",
    "description",
    "particulars",
]


def clean_amount_str(val: str) -> str:
    """
    Cleans raw amount string by stripping commas, currency symbols, and spaces.
    Preserves negative signs or decimals.
    """
    if not val:
        return "0.00"
    
    s = str(val).strip()
    # Remove currency symbols and labels
    s = re.sub(r"[₹$€£\s]|INR|Rs\.?|/-", "", s, flags=re.IGNORECASE)
    # Remove commas
    s = s.replace(",", "")
    # Remove trailing or leading Cr / Dr indicators
    s = re.sub(r"(?:\b|(?<=\d))(?:cr|dr)\b", "", s, flags=re.IGNORECASE).strip()
    # Check for empty or dashes
    if not s or s in ["-", "--", "NA", "N/A", "nil", "NIL"]:
        return "0.00"
    
    return s


def parse_decimal_amount(val: Any) -> Decimal:
    """
    Converts string to Decimal strictly without float conversions.
    Quantizes to 2 decimal places.
    """
    if val is None:
        return Decimal("0.00")
    
    clean_str = clean_amount_str(str(val))
    try:
        dec = Decimal(clean_str)
        return dec.quantize(Decimal("0.01"))
    except InvalidOperation:
        # If string has trailing Dr / Cr
        m = re.match(r"^([\d.]+)\s*(cr|dr)?$", clean_str, flags=re.IGNORECASE)
        if m:
            try:
                dec = Decimal(m.group(1))
                return dec.quantize(Decimal("0.01"))
            except InvalidOperation:
                pass
        return Decimal("0.00")


def parse_single_amount_with_drcr(amount_str: str, drcr_indicator: Optional[str] = None) -> Tuple[Decimal, Decimal]:
    """
    Parses single amount column where debit vs credit is marked by 'Dr' / 'Cr'
    in the same column or a separate indicator column.
    Returns (debit, credit) as Decimals.
    """
    combined = f"{amount_str} {drcr_indicator or ''}".strip().lower()
    amount = parse_decimal_amount(amount_str)
    
    if "dr" in combined:
        return (amount, Decimal("0.00"))
    elif "cr" in combined:
        return (Decimal("0.00"), amount)
    
    # Default: if no indicator, return as credit if positive, or debit if negative
    if amount < Decimal("0.00"):
        return (abs(amount), Decimal("0.00"))
    return (Decimal("0.00"), amount)


def parse_date_with_formats(val: str, formats: List[str]) -> Optional[date]:
    """
    Tries each specific bank date format explicitly.
    Applies OCR artifact cleaning (quotes, brackets, missing slashes).
    """
    if not val:
        return None
    
    cleaned = str(val).strip()
    cleaned = re.sub(r"^[‘\x27\"`\(\[\{\|\s.,]+", "", cleaned)
    cleaned = re.sub(r"[‘\x27\"`\)\}\]\|\s.,]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    
    # 1. Exact bank formats
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    # 2. OCR character substitutions in date strings
    s_fix = cleaned
    if re.search(r"\d", s_fix) or "/" in s_fix or "-" in s_fix or "." in s_fix:
        s_fix = re.sub(r"(?<=\d)[oO]|[oO](?=\d)", "0", s_fix)
        s_fix = re.sub(r"^[oO](?=[0-9A-Za-z])", "0", s_fix)
        s_fix = re.sub(r"(?<=\d)[sS]|[sS](?=\d)", "5", s_fix)
        s_fix = re.sub(r"[mM](?=[0-9])", "/", s_fix)
        s_fix = re.sub(r"(?<=\d)[mM]", "/", s_fix)

    # 3. OCR missing/misclassified slashes repair
    # e.g. 0306/18 -> 03/06/18
    s_fix = re.sub(r"\b(\d{2})(\d{2})[/.](\d{2,4})\b", r"\1/\2/\3", s_fix)
    # e.g. 03/0618 -> 03/06/18
    s_fix = re.sub(r"\b(\d{2})[/.](\d{2})(\d{2,4})\b", r"\1/\2/\3", s_fix)
    # e.g. 05/618 or OSM618 -> 05/06/18
    s_fix = re.sub(r"\b([0-3]\d)[/.]?([1-9])(\d{2})\b", r"\1/0\2/\3", s_fix)
    # e.g. 186/18 -> 18/06/18
    s_fix = re.sub(r"\b([0-3]\d)([1-9])[/.](\d{2,4})\b", r"\1/0\2/\3", s_fix)
    # e.g. 1916/18 -> 19/06/18
    s_fix = re.sub(r"\b([0-3]\d)1([0-1]\d)[/.](\d{2,4})\b", r"\1/\2/\3", s_fix)
    # e.g. 0910618 -> 09/06/18
    s_fix = re.sub(r"\b([0-3]\d)1([0-1]\d)(\d{2})\b", r"\1/\2/\3", s_fix)
    # e.g. 220618 -> 22/06/18
    s_fix = re.sub(r"\b([0-3]\d)([0-1]\d)(?:0?18|2018)\b", r"\1/\2/18", s_fix)
    s_fix = re.sub(r"\b([0-3]\d)([0-1]\d)(\d{2,4})\b", r"\1/\2/\3", s_fix)

    for fmt in formats:
        try:
            return datetime.strptime(s_fix, fmt).date()
        except ValueError:
            continue

    # 4. Standard fallback delimiters
    for fmt in ["%d/%m/%y", "%d/%m/%Y", "%d-%m-%y", "%d-%m-%Y", "%d.%m.%y", "%d.%m.%Y"]:
        try:
            return datetime.strptime(s_fix, fmt).date()
        except ValueError:
            continue

    return None


def is_skip_row(cells: List[str]) -> bool:
    """
    Checks if a row is a header, footer, page number, or opening/closing balance summary row.
    Avoids false positives when transactions have words like 'transfer' or 'salary'.
    """
    if not cells or all(not str(c).strip() for c in cells):
        return True

    joined_text = " ".join(str(c).lower().strip() for c in cells if c).strip()

    # Exact summary phrases (e.g. standalone "B/F" or "OPENING BALANCE")
    exact_skips = {"b/f", "c/f", "opening balance", "closing balance", "brought forward", "carried forward", "grand total", "total"}
    for cell in cells:
        clean_c = str(cell).lower().strip()
        if clean_c in exact_skips:
            # If the row only has this label and at most a balance number, it is a summary row
            other_cells = [str(c).strip() for c in cells if str(c).lower().strip() != clean_c and str(c).strip()]
            if len(other_cells) <= 1:
                return True

    # Repeated headers or page footers
    if ("date" in joined_text and "narration" in joined_text) or ("txn date" in joined_text and "balance" in joined_text):
        return True
    if "statement of account" in joined_text or "account statement" in joined_text:
        return True
    if re.match(r"^page\s+\d+(\s+of\s+\d+)?$", joined_text):
        return True

    return False


def sort_txns_oldest_first(txns: List[ParsedTxn]) -> List[ParsedTxn]:
    """
    Ensures transaction list is sorted strictly in chronological order (oldest-first).
    Stable sort preserves original relative order for txns occurring on the same date.
    """
    return sorted(txns, key=lambda t: t.txn_date)
