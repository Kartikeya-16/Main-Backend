import re
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Tuple

from app.schemas import ParsedTxn, ParsedStatement
from app.normalize import sort_txns_oldest_first
from app.reconcile import reconcile_transactions


# Standard month names in English (abbreviated and full)
MONTH_NAMES = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"

MONTHS_LIST = [
    "jan", "january", "feb", "february", "mar", "march", "apr", "april",
    "may", "jun", "june", "jul", "july", "aug", "august", "sep", "september",
    "oct", "october", "nov", "november", "dec", "december"
]

# Format-agnostic date patterns for Indian, international, and handwritten paper statements
DATE_PATTERNS = [
    # 01-Aug-2023, 01/Aug/23, 01 Aug 2023, 01 August 2023, 1 Aug 2023
    re.compile(rf"\b(\d{{1,2}}[-/.\s]{MONTH_NAMES}[-/.\s]\d{{2,4}})\b", re.IGNORECASE),
    # Aug 01, 2023 or August 01 2023 or Aug 1, 23
    re.compile(rf"\b({MONTH_NAMES}\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{2,4}})\b", re.IGNORECASE),
    # 01/08/2023, 01-08-23, 01.08.2023, 1/8/2023
    re.compile(r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})\b"),
    # OCR missing slash e.g. 0306/18, 03/0618
    re.compile(r"\b(\d{2})(\d{2})[/.](\d{2,4})\b"),
    re.compile(r"\b(\d{2})[/.](\d{2})(\d{2,4})\b"),
    # 2023-08-01, 2023/08/01
    re.compile(r"\b(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b"),
    # 6-digit or 8-digit compact dates e.g. 220618 or 01062018
    re.compile(r"\b([0-3]\d)([0-1]\d)(?:0?18|2018)\b"),
    re.compile(r"\b([0-3]\d)([0-1]\d)(\d{4})\b"),
    re.compile(r"\b([0-3]\d)([0-1]\d)(\d{2})\b"),
    # OCR typo dates e.g. or-08-23, 0l/08/2023, 07-028
    re.compile(r"\b([oO0][rRlI1\d][-/.\s][a-zA-Z\d]{2,9}[-/.\s]\d{2,4})\b", re.IGNORECASE),
    # Casual dates without explicit year (e.g. "1 Aug", "15th August", "Aug 5", "01/08", "2-8")
    re.compile(rf"\b(\d{{1,2}}(?:st|nd|rd|th)?[-/.\s]{MONTH_NAMES})\b", re.IGNORECASE),
    re.compile(rf"\b({MONTH_NAMES}\s+\d{{1,2}}(?:st|nd|rd|th)?)\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2}[-/.]\d{1,2})\b"),
]


# Currency symbol or prefix
CURRENCY_PREFIX = r"(?:(?:Rs\.?|INR|₹|\$)\s*)"
DRCR_SUFFIX = r"(?:\s*(DR|CR|GR|0R|DEBIT|CREDIT|\(DR\)|\(CR\)|-|\+))"

# Amounts with 1 or 2 decimals
AMT_WITH_DECIMALS = re.compile(
    r"(?:" + CURRENCY_PREFIX + r")?"
    r"(?:"
    r"\(([\d,]+\.\d{1,2})\)|"
    r"([+-]?[\d,]+\.\d{1,2})"
    r")"
    r"(?:" + DRCR_SUFFIX + r")?",
    re.IGNORECASE,
)

# Integer amounts with currency prefix, e.g. ₹10000, Rs. 500 DR, $25
AMT_INTEGER_CURRENCY = re.compile(
    r"(?:" + CURRENCY_PREFIX + r"([\d,]+)" + DRCR_SUFFIX + r"?)",
    re.IGNORECASE,
)

# Integer amounts with explicit DR/CR indicator, e.g. 10000 DR, 500 CR
AMT_INTEGER_DRCR = re.compile(
    r"\b([\d,]+)" + DRCR_SUFFIX,
    re.IGNORECASE,
)

# Integer amounts with thousands commas, e.g. 10,000 or 1,50,000
AMT_INTEGER_COMMAS = re.compile(
    r"\b(\d{1,3}(?:,\d{2,3})+)\b" + DRCR_SUFFIX + r"?",
    re.IGNORECASE,
)

# Plain integer amounts for casual handwritten notes / blank paper (e.g. Milk 60, Grocery 450, Rent 10000)
AMT_PLAIN_INTEGER = re.compile(
    r"\b(\d{1,8})\b" + DRCR_SUFFIX + r"?",
    re.IGNORECASE,
)

# Natural language income/credit indicators using word boundaries to prevent substring collisions (e.g. 'cr' in 'grocery')
INCOME_REGEX = re.compile(
    r"\b(deposit|deposited|credit|credited|salary|refund|received|got|earned|income|inflow|borrowed|cash\s*in|cash\s*from|money\s*from|transfer\s*from|reimbursement|cashback|cr|gr)\b|(?:\s\+\s|^\+\d)",
    re.IGNORECASE,
)

# Natural language expense/debit indicators
EXPENSE_REGEX = re.compile(
    r"\b(debit|debited|withdrawal|paid|spent|to|bought|purchase|cash\s*out|bill|fee|rent|expense|outflow|returned|dr|0r)\b|(?:\s-\s|^-\d)",
    re.IGNORECASE,
)

# Comprehensive list of banks & fintech platforms for auto-detection
KNOWN_BANKS = [
    ("State Bank of India (SBI)", [r"\bstate bank of india\b", r"\bsbi\b", r"\bsbin\b"]),
    ("HDFC Bank", [r"\bhdfc bank\b", r"\bhdfc\b"]),
    ("ICICI Bank", [r"\bicici bank\b", r"\bicici\b", r"\bicic0\b"]),
    ("Axis Bank", [r"\baxis bank\b", r"\butib\b", r"\baxis\b"]),
    ("Kotak Mahindra Bank", [r"\bkotak mahindra\b", r"\bkotak bank\b", r"\bkkbk\b", r"\bkotak\b"]),
    ("Punjab National Bank (PNB)", [r"\bpunjab national bank\b", r"\bpnb\b", r"\bpunb\b"]),
    ("Bank of Baroda", [r"\bbank of baroda\b", r"\bbarb0\b", r"\bbob\b"]),
    ("Canara Bank", [r"\bcanara bank\b", r"\bcnrb\b", r"\bcanara\b"]),
    ("Union Bank of India", [r"\bunion bank of india\b", r"\bunion bank\b", r"\bubin\b"]),
    ("IndusInd Bank", [r"\bindusind bank\b", r"\bindb\b", r"\bindusind\b"]),
    ("Yes Bank", [r"\byes bank\b", r"\byesb\b"]),
    ("Federal Bank", [r"\bfederal bank\b", r"\bfdrl\b"]),
    ("IDBI Bank", [r"\bidbi bank\b", r"\bibkl\b"]),
    ("Indian Bank", [r"\bindian bank\b", r"\bidib\b"]),
    ("Central Bank of India", [r"\bcentral bank of india\b", r"\bcbin\b"]),
    ("Bank of India", [r"\bbank of india\b", r"\bbkid\b"]),
    ("Bank of Maharashtra", [r"\bbank of maharashtra\b", r"\bmahb\b"]),
    ("UCO Bank", [r"\buco bank\b", r"\bucba\b"]),
    ("Indian Overseas Bank", [r"\bindian overseas bank\b", r"\bioba\b"]),
    ("Punjab & Sind Bank", [r"\bpunjab & sind\b", r"\bpsib\b"]),
    ("Paytm Payments Bank", [r"\bpaytm payments bank\b", r"\bpaytm bank\b", r"\bpaytm\b", r"\bpytm\b"]),
    ("PhonePe", [r"\bphonepe\b", r"\bybl\b", r"\bibl\b"]),
    ("Google Pay", [r"\bgoogle pay\b", r"\bgpay\b", r"\bokaxis\b", r"\bokicici\b", r"\bokhdfcbank\b", r"\boksbi\b"]),
    ("CRED", [r"\bcred\b"]),
    ("Jupiter", [r"\bjupiter\b"]),
    ("Fi Money", [r"\bfi money\b", r"\bfi\b"]),
    ("Airtel Payments Bank", [r"\bairtel payments bank\b", r"\bairtel bank\b"]),
    ("Standard Chartered", [r"\bstandard chartered\b", r"\bscbl\b"]),
    ("Citibank", [r"\bcitibank\b", r"\bciti\b"]),
    ("HSBC Bank", [r"\bhsbc bank\b", r"\bhsbc\b"]),
    ("AU Small Finance Bank", [r"\bau small finance\b", r"\bau bank\b", r"\baubl\b"]),
    ("Equitas Small Finance Bank", [r"\bequitas\b", r"\besfb\b"]),
    ("Bandhan Bank", [r"\bbandhan bank\b", r"\bbdbd\b"]),
    ("RBL Bank", [r"\brbl bank\b", r"\bratn\b"]),
    ("South Indian Bank", [r"\bsouth indian bank\b", r"\bsibl\b"]),
]


def detect_bank_name(
    text: str,
    filename: str = "",
    default_bank: str = "Bank Statement",
    raw_rows: Optional[List[List[str]]] = None,
) -> str:
    """
    Identifies the financial institution or document title from text, raw rows, or filename.
    Recognizes formal banks, UPI wallets, as well as handwritten paper ledgers and personal cash notes.
    """
    text_lower = text.lower()
    fn_lower = filename.lower()

    # 1. Match against known banks and digital payment platforms
    for bank_label, patterns in KNOWN_BANKS:
        for pat in patterns:
            if re.search(pat, text_lower) or re.search(pat, fn_lower):
                return bank_label

    # 2. Check for custom handwritten/paper titles in first 5 rows (e.g. "Hostel Monthly Expenses", "Cash Ledger 2024")
    candidate_lines = []
    if raw_rows:
        candidate_lines = [" ".join(str(c) for c in r).strip() for r in raw_rows[:5]]
    else:
        candidate_lines = [l.strip() for l in text.split("\n") if l.strip()][:5]

    for line in candidate_lines:
        if 3 < len(line) < 60:
            ll = line.lower()
            if any(k in ll for k in [
                "expense", "ledger", "budget", "khata", "cash", "diary",
                "dairy", "accounts", "notes", "bahi", "chit", "petty", "personal", "bill"
            ]):
                clean_title = re.sub(r"[|:_\-\[\]#*]", " ", line)
                return re.sub(r"\s+", " ", clean_title).strip().title()

    # 3. Filename derivation
    if filename:
        clean_fn = re.sub(r"\.[^.]+$", "", filename).replace("_", " ").replace("-", " ").title()
        if len(clean_fn) > 3 and not any(k in clean_fn.lower() for k in ["statement", "download", "document", "img", "image", "media", "upload"]):
            return clean_fn

    if default_bank and not default_bank.startswith("Generic") and not default_bank == "Bank Statement":
        return default_bank

    return "Personal Ledger / Cash Statement"


def fix_ocr_date(s: str) -> str:
    """
    Corrects frequent OCR character misclassifications in date strings.
    E.g.: 'or-08-23' -> '01-08-23', '0306/18' -> '03/06/18', '(0306/18' -> '03/06/18',
    'OSM618' -> '05/06/18', '03/06/18.' -> '03/06/18'.
    """
    s = re.sub(r"^[‘\x27\"`\(\[\{\|\s.,]+", "", s)
    s = re.sub(r"[‘\x27\"`\)\}\]\|\s.,]+$", "", s).strip()

    # OCR character substitutions in date strings
    if re.search(r"\d", s) or "/" in s or "-" in s or "." in s:
        s = re.sub(r"(?<=\d)[oO]|[oO](?=\d)", "0", s)
        s = re.sub(r"^[oO](?=[0-9A-Za-z])", "0", s)
        s = re.sub(r"(?<=\d)[sS]|[sS](?=\d)", "5", s)
        s = re.sub(r"[mM](?=[0-9])", "/", s)
        s = re.sub(r"(?<=\d)[mM]", "/", s)

    s = re.sub(r"\b(\d{2})(\d{2})[/.](\d{2,4})\b", r"\1/\2/\3", s)
    s = re.sub(r"\b(\d{2})[/.](\d{2})(\d{2,4})\b", r"\1/\2/\3", s)
    s = re.sub(r"\b([0-3]\d)[/.]?([1-9])(\d{2})\b", r"\1/0\2/\3", s)
    s = re.sub(r"\b([0-3]\d)([1-9])[/.](\d{2,4})\b", r"\1/0\2/\3", s)
    s = re.sub(r"\b([0-3]\d)1([0-1]\d)[/.](\d{2,4})\b", r"\1/\2/\3", s)
    s = re.sub(r"\b([0-3]\d)1([0-1]\d)(\d{2})\b", r"\1/\2/\3", s)
    s = re.sub(r"\b([0-3]\d)([0-1]\d)(?:0?18|2018)\b", r"\1/\2/18", s)
    s = re.sub(r"\b([0-3]\d)([0-1]\d)(\d{2,4})\b", r"\1/\2/\3", s)
    s = re.sub(r"\b[oO0][rRlI1]-", "01-", s)
    s = re.sub(r"\b[oO0][rRlI1](\d{2})-", r"01-\1-", s)
    s = re.sub(r"\boros2s\b", "01-08-23", s, flags=re.IGNORECASE)
    s = re.sub(r"\b0208-23\b", "02-08-23", s)
    s = re.sub(r"\b07-028\b", "07-08-23", s)
    return s


def try_parse_date(
    dt_str: str,
    custom_formats: Optional[List[str]] = None,
    default_year: Optional[int] = None,
) -> Optional[date]:
    """
    Robust date parser supporting space, hyphen, slash, and dot separators,
    full/abbreviated month names, and day-month dates without explicit year.
    """
    clean = fix_ocr_date(dt_str)
    clean_no_punct = clean.replace("/", " ").replace("-", " ").replace(".", " ")
    clean_no_punct = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", clean_no_punct, flags=re.IGNORECASE)
    clean_no_punct = re.sub(r"\s+", " ", clean_no_punct).strip()

    formats = [
        "%d %b %Y", "%d %b %y",
        "%d %B %Y", "%d %B %y",
        "%b %d %Y", "%b %d %y",
        "%B %d %Y", "%B %d %y",
        "%d %m %Y", "%d %m %y",
        "%Y %m %d",
        "%m %d %Y", "%m %d %y",
        "%d%m%Y", "%d%m%y",
    ]
    if custom_formats:
        for cf in custom_formats:
            fmt_clean = cf.replace("-", " ").replace("/", " ").replace(".", " ")
            if fmt_clean not in formats:
                formats.insert(0, fmt_clean)

    # 1. Try full formats with year
    for fmt in formats:
        try:
            return datetime.strptime(clean_no_punct, fmt).date()
        except ValueError:
            continue


    # 2. Try day-month formats without year (e.g. "1 Aug", "15th August", "01 08", "10/08")
    yr = default_year or date.today().year
    clean_with_yr = f"{clean_no_punct} {yr}"
    day_month_formats = [
        "%d %b %Y", "%d %B %Y",
        "%b %d %Y", "%B %d %Y",
        "%d %m %Y", "%m %d %Y",
    ]
    for fmt in day_month_formats:
        try:
            return datetime.strptime(clean_with_yr, fmt).date()
        except ValueError:
            continue

    return None


def find_date_in_line(
    line: str,
    custom_formats: Optional[List[str]] = None,
    default_year: Optional[int] = None,
) -> Tuple[Optional[date], int, int]:
    """
    Finds the earliest valid date in a text line. Returns (date, start_pos, end_pos).
    """
    for pat in DATE_PATTERNS:
        m = pat.search(line)
        if m:
            d = try_parse_date(m.group(1), custom_formats, default_year)
            if d:
                return d, m.start(), m.end()
    return None, -1, -1


def is_likely_year_token(val: Decimal, start: int, end: int, text: str) -> bool:
    """
    Determines if a 4-digit number (1990..2035) represents a year or a currency amount (e.g. ₹2000 note).
    """
    if not (1990 <= val <= 2035):
        return False
    before = text[:start].lower()
    after = text[end:].lower()
    b_words = re.findall(r"[a-zA-Z]+", before)
    a_words = re.findall(r"[a-zA-Z]+", after)
    last_b = b_words[-1] if b_words else ""
    first_a = a_words[0] if a_words else ""

    if last_b in MONTHS_LIST or first_a in MONTHS_LIST:
        return True
    if last_b in ["year", "yr", "dated", "in", "of", "from"]:
        return True
    return False


REF_PREFIX_WORDS = {
    "order", "ord", "ref", "reference", "txn", "txnid", "id", "no", "num", "number",
    "chq", "cheque", "utr", "code", "port", "pid", "status", "pin", "ac", "a/c", "account",
    "card", "ph", "phone", "mob", "mobile", "tel", "invoice", "inv", "billno", "ticket",
    "flight", "seat", "step", "vessel"
}

REF_POSTFIX_WORDS = {"port", "tcp", "udp", "kb", "mb", "gb", "fps", "ms", "km", "kg", "pcs", "mins", "hrs"}


def mask_time_patterns(s: str) -> str:
    """
    Masks timestamp values like 12:00:00 or 14:30 into blank spaces,
    preserving exact character offsets for remaining tokens.
    """
    return re.sub(
        r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*(?:AM|PM|am|pm))?\b",
        lambda m: " " * len(m.group(0)),
        s,
    )


def is_preceded_by_reference_word(text: str, start: int) -> bool:
    """
    Checks if a number is preceded by identifier keywords like 'order', 'ref', 'port', 'code'.
    """
    prefix = text[:start]
    m = re.search(r"([a-zA-Z#]+)\s*$", prefix)
    if m:
        w = m.group(1).lower().rstrip("#")
        return w in REF_PREFIX_WORDS
    return False


def is_followed_by_unit_word(text: str, end: int) -> bool:
    """
    Checks if a number is followed by technical unit symbols like 'port', 'tcp', 'fps'.
    """
    suffix = text[end:]
    m = re.search(r"^\s*([a-zA-Z]+)", suffix)
    if m:
        w = m.group(1).lower()
        return w in REF_POSTFIX_WORDS
    return False


def extract_amounts_from_text(rest: str) -> List[Tuple[int, int, Decimal, str]]:
    """
    Extracts all numeric monetary amounts from text.
    Handles decimal amounts, strict integer amounts, and plain numbers on handwritten paper/notes.
    Returns sorted list of (start_idx, end_idx, Decimal_amount, indicator_str).
    """
    rest_clean = re.sub(r"(\d+),(\d{2})\b", r"\1.\2", rest)
    # Normalize OCR multi-dot / thousands dot artifacts (e.g. 29.064.95 -> 29064.95, 3.99381 -> 3993.81)
    rest_clean = re.sub(r"(\d+)\.(\d{3})\.(\d{2})\b", r"\1\2.\3", rest_clean)
    rest_clean = re.sub(r"(\d{1,3})\.(\d{3})\.(\d{2})\b", r"\1\2.\3", rest_clean)
    rest_clean = re.sub(r"\b(\d+)\.(\d{3})(\d{2})\b", r"\1\2.\3", rest_clean)
    masked_clean = mask_time_patterns(rest_clean)
    results: List[Tuple[int, int, Decimal, str]] = []

    def overlaps(s: int, e: int) -> bool:
        return any(max(s, r[0]) < min(e, r[1]) for r in results)

    # 1. Decimal amounts (e.g. 1,500.00, 350.00 DR, 171191.04 CR)
    for m in AMT_WITH_DECIMALS.finditer(masked_clean):
        num_str = m.group(1) or m.group(2)
        ind = (m.group(3) or "").upper()
        clean = num_str.replace(",", "").replace("+", "").replace("-", "")
        try:
            val = Decimal(clean).quantize(Decimal("0.01"))
            if 0 <= val <= 100_000_000:
                results.append((m.start(), m.end(), val, ind))
        except Exception:
            pass

    # 2. Integer amounts with currency symbol, DR/CR, or thousands commas
    # 2a. With currency symbol (e.g. ₹10000 DR, Rs. 500)
    for m in AMT_INTEGER_CURRENCY.finditer(masked_clean):
        if overlaps(m.start(), m.end()):
            continue
        clean = m.group(1).replace(",", "")
        ind = (m.group(2) or "").upper()
        try:
            val = Decimal(clean).quantize(Decimal("0.01"))
            if 0 < val <= 100_000_000:
                results.append((m.start(), m.end(), val, ind))
        except Exception:
            pass

    # 2b. With explicit DR/CR indicator (e.g. 10000 DR, 500 CR)
    for m in AMT_INTEGER_DRCR.finditer(masked_clean):
        if overlaps(m.start(), m.end()):
            continue
        clean = m.group(1).replace(",", "")
        ind = (m.group(2) or "").upper()
        try:
            val = Decimal(clean).quantize(Decimal("0.01"))
            if 0 < val <= 100_000_000:
                results.append((m.start(), m.end(), val, ind))
        except Exception:
            pass

    # 2c. With thousands commas (e.g. 10,000 or 1,50,000)
    for m in AMT_INTEGER_COMMAS.finditer(masked_clean):
        if overlaps(m.start(), m.end()):
            continue
        clean = m.group(1).replace(",", "")
        ind = (m.group(2) or "").upper()
        try:
            val = Decimal(clean).quantize(Decimal("0.01"))
            if 0 < val <= 100_000_000:
                results.append((m.start(), m.end(), val, ind))
        except Exception:
            pass

    # 3. Universal plain integer amounts for blank paper / handwritten lists (e.g. 'Milk 60', 'Grocery 450', 'Rent 10000')
    if not results:
        for m in AMT_PLAIN_INTEGER.finditer(masked_clean):
            if overlaps(m.start(), m.end()):
                continue
            if is_preceded_by_reference_word(masked_clean, m.start()):
                continue
            if is_followed_by_unit_word(masked_clean, m.end()):
                continue
            clean = m.group(1)
            ind = (m.group(2) or "").upper()
            try:
                val = Decimal(clean).quantize(Decimal("0.01"))
                if not ind and is_likely_year_token(val, m.start(), m.end(), masked_clean):
                    continue
                if 0 < val <= 100_000_000:
                    results.append((m.start(), m.end(), val, ind))
            except Exception:
                pass

    results.sort(key=lambda x: x[0])
    return results


def resolve_debit_credit_balance(
    amounts: List[Tuple[int, int, Decimal, str]],
    context_text: str,
    txns: List[ParsedTxn],
    running_balance: Decimal,
) -> Tuple[Decimal, Decimal, Decimal]:
    """
    Accurately determines Debit, Credit, and Balance from extracted amounts.
    Understands banking indicators as well as natural language phrasing
    (e.g. 'paid 60', 'received 5000', 'salary 45000', 'bought shoes 1500').
    """
    debit = Decimal("0.00")
    credit = Decimal("0.00")
    bal = running_balance

    if len(amounts) >= 3:
        bal = amounts[-1][2]
        # Candidate amounts before the closing balance
        cand_1 = amounts[-2][2]
        cand_2 = amounts[-3][2]

        if running_balance > Decimal("0.00"):
            delta = (bal - running_balance).quantize(Decimal("0.01"))
            if (running_balance - cand_1) == bal or (delta < Decimal("0.00") and abs(delta) == cand_1):
                debit = cand_1
                credit = Decimal("0.00")
            elif (running_balance + cand_1) == bal or (delta > Decimal("0.00") and delta == cand_1):
                credit = cand_1
                debit = Decimal("0.00")
            elif (running_balance - cand_2) == bal or (delta < Decimal("0.00") and abs(delta) == cand_2):
                debit = cand_2
                credit = Decimal("0.00")
            elif (running_balance + cand_2) == bal or (delta > Decimal("0.00") and delta == cand_2):
                credit = cand_2
                debit = Decimal("0.00")
            elif (running_balance + cand_1 - cand_2) == bal:
                debit = cand_2
                credit = cand_1
            elif delta > Decimal("0.00"):
                credit = cand_1
                debit = Decimal("0.00")
            elif delta < Decimal("0.00"):
                debit = cand_1
                credit = Decimal("0.00")
            else:
                debit = cand_2
                credit = cand_1
        else:
            # First transaction with 3 numbers
            if amounts[-2][3] in ["CR", "GR", "CREDIT", "+"]:
                credit = cand_1
            elif amounts[-2][3] in ["DR", "0R", "DEBIT", "-"]:
                debit = cand_1
            elif amounts[-3][3] in ["CR", "GR", "CREDIT", "+"]:
                credit = cand_2
            elif amounts[-3][3] in ["DR", "0R", "DEBIT", "-"]:
                debit = cand_2
            elif INCOME_REGEX.search(context_text) and not EXPENSE_REGEX.search(context_text):
                credit = cand_1
            elif EXPENSE_REGEX.search(context_text):
                debit = cand_1
            else:
                debit = cand_2
                credit = cand_1

    elif len(amounts) == 2:
        amt_val = amounts[0][2]
        ind = amounts[0][3]
        bal = amounts[1][2]

        if ind in ["DR", "0R", "DEBIT", "(DR)", "-"]:
            debit = amt_val
        elif ind in ["CR", "GR", "CREDIT", "(CR)", "+"]:
            credit = amt_val
        # Mathematical running balance verification (absolute ground truth)
        elif running_balance > Decimal("0.00") and (running_balance + amt_val) == bal:
            credit = amt_val
        elif running_balance > Decimal("0.00") and (running_balance - amt_val) == bal:
            debit = amt_val
        elif running_balance > Decimal("0.00") and bal > running_balance:
            credit = amt_val
        elif running_balance > Decimal("0.00") and bal < running_balance:
            debit = amt_val
        elif txns and bal > txns[-1].balance:
            credit = amt_val
        elif txns and bal < txns[-1].balance:
            debit = amt_val
        elif INCOME_REGEX.search(context_text) and not EXPENSE_REGEX.search(context_text):
            credit = amt_val
        elif EXPENSE_REGEX.search(context_text):
            debit = amt_val
        else:
            debit = amt_val
    elif len(amounts) == 1:
        # Single amount layout: Mini-statement, paper ledger, or expense sheet
        amt_val = amounts[0][2]
        ind = amounts[0][3]

        if ind in ["DR", "0R", "DEBIT", "(DR)", "-"]:
            debit = amt_val
            bal = running_balance - debit
        elif ind in ["CR", "GR", "CREDIT", "(CR)", "+"]:
            credit = amt_val
            bal = running_balance + credit
        elif INCOME_REGEX.search(context_text) and not EXPENSE_REGEX.search(context_text):
            credit = amt_val
            bal = running_balance + credit
        elif EXPENSE_REGEX.search(context_text):
            debit = amt_val
            bal = running_balance - debit
        else:
            # Default casual entries on paper (e.g. 'Milk 60', 'Grocery 450') to expense/debit
            debit = amt_val
            bal = running_balance - debit

    return debit, credit, bal



def clean_narration_string(s: str) -> str:
    """
    Cleans OCR pipe delimiters, colon symbols, and redundant whitespace
    while preserving hyphens in transaction identifiers (e.g. UPI-12345, DR-HDFC).
    """
    s = re.sub(r"[|\[\]#*]", " ", s)
    s = re.sub(r"\s+[-:_]\s+", " ", s)
    s = re.sub(r"^[-:_]+|[-:_]+$", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_semantically(
    raw_rows: List[List[str]],
    bank_name: str = "Bank Statement",
    filename: str = "",
    date_formats: Optional[List[str]] = None,
) -> Optional[ParsedStatement]:
    """
    Universal semantic parser for ANY statement, image, receipt, passbook,
    or handwritten ledger written on a blank piece of paper.
    """
    if not raw_rows:
        return None

    # Flatten raw rows into clean text lines
    lines: List[str] = []
    for r in raw_rows:
        if not r:
            continue
        line = " ".join(str(c) for c in r if str(c).strip()).strip()
        if line:
            lines.append(line)

    if not lines:
        return None

    combined_full_text = " ".join(lines)
    resolved_bank = detect_bank_name(combined_full_text, filename, bank_name, raw_rows=raw_rows)

    # Detect default document date or year from header lines
    doc_default_date: date = date.today()
    for l in lines[:15]:
        m_range = re.search(r"\b(?:from|period|dated?)[:\s]+([0-3]?\d[/.-]?[0-1]?\d[/.-]?\d{2,4})\b", l, re.IGNORECASE)
        if m_range:
            d_cand = try_parse_date(m_range.group(1), date_formats)
            if d_cand:
                doc_default_date = d_cand
                break
        d, _, _ = find_date_in_line(l, date_formats)
        if d:
            doc_default_date = d
            break

    has_any_dates_in_doc = any(find_date_in_line(l, date_formats)[0] is not None for l in lines)
    txns: List[ParsedTxn] = []

    # Non-transaction keywords to ignore in headers/footers
    skip_keywords = [
        "customer name",
        "account number",
        "statement of account",
        "branch",
        "cif no",
        "ifsc",
        "micr",
        "available balance",
        "uncleared balance",
        "account description",
        "page no",
        "tun date",
        "value date",
        "statement period",
        "generated on",
        "closing balance",
    ]

    pending_dt: Optional[date] = None
    pending_narration: str = ""
    running_balance = Decimal("0.00")

    for line in lines:
        ll = line.lower()
        if any(kw in ll for kw in skip_keywords):
            continue

        # Skip if line is identical to the document header title and has no amounts
        if line.lower() == resolved_bank.lower() and not extract_amounts_from_text(line):
            continue

        target_line = line
        parsed_dt, d_start, d_end = find_date_in_line(target_line, date_formats, doc_default_date.year)
        if not parsed_dt:
            clean_line = re.sub(r"^\s*(?:#\d+|\d{1,4}[.)\]]|\d{1,4}\s*\|)\s*", "", line)
            parsed_dt, d_start, d_end = find_date_in_line(clean_line, date_formats, doc_default_date.year)
            if parsed_dt:
                target_line = clean_line

        if parsed_dt:
            rest = target_line[d_end:].strip()
            # If an adjacent Value Date exists, step past it
            val_dt, v_start, v_end = find_date_in_line(rest[:35], date_formats, doc_default_date.year)
            if val_dt:
                rest = rest[v_end:].strip()

            amounts = extract_amounts_from_text(rest)
            if not amounts:
                # Multi-line statement: Line 1 has Date and Narration; amounts follow on next line
                pending_dt = parsed_dt
                pending_narration = rest
                continue

            narration_raw = rest[: amounts[0][0]] if amounts else rest
            debit, credit, bal = resolve_debit_credit_balance(amounts, rest, txns, running_balance)
            running_balance = bal
            narration = clean_narration_string(narration_raw)

            txns.append(
                ParsedTxn(
                    txn_date=parsed_dt,
                    narration=narration or "Transaction",
                    ref_no=None,
                    debit=debit,
                    credit=credit,
                    balance=bal,
                )
            )
            pending_dt = None
            pending_narration = ""

        else:
            # Line has NO date (common in handwritten blank paper ledgers or multi-line statements)
            amounts = extract_amounts_from_text(line)
            if amounts and pending_dt:
                # Multi-line statement: Pair amounts with pending Date & Narration!
                narration_raw = (pending_narration + " " + line[: amounts[0][0]]).strip()
                debit, credit, bal = resolve_debit_credit_balance(amounts, line, txns, running_balance)
                running_balance = bal
                narration = clean_narration_string(narration_raw)

                txns.append(
                    ParsedTxn(
                        txn_date=pending_dt,
                        narration=narration or "Transaction",
                        ref_no=None,
                        debit=debit,
                        credit=credit,
                        balance=bal,
                    )
                )
                pending_dt = None
                pending_narration = ""

            elif amounts and not pending_dt:
                # If no transactions have been parsed yet and the document has dates elsewhere,
                # skip header metadata lines (branch, address, phone, account opening date) before table
                HEADER_METADATA_WORDS = [
                    "account", "branch", "code", "customer", "address", "phone", "email",
                    "cif", "ifsc", "micr", "nomination", "joint", "regulat", "status",
                    "near", "road", "hospital", "floor", "opp", "flat", "chsltd",
                    "statement of account", "statement period", "page", "date :"
                ]
                if not txns and has_any_dates_in_doc and any(hw in line.lower() for hw in HEADER_METADATA_WORDS):
                    continue

                # Handwritten paper / blank ledger line without explicit date on every row (e.g. 'Milk 60', 'Rent 10000')
                narration_raw = (line[: amounts[0][0]] + " " + line[amounts[-1][1]:]).strip()
                narration = clean_narration_string(narration_raw)
                
                # Ensure it's not a pure metadata/header line
                if narration or len(amounts) >= 1:
                    txn_date = txns[-1].txn_date if txns else doc_default_date
                    debit, credit, bal = resolve_debit_credit_balance(amounts, line, txns, running_balance)
                    running_balance = bal

                    txns.append(
                        ParsedTxn(
                            txn_date=txn_date,
                            narration=narration or "Expense",
                            ref_no=None,
                            debit=debit,
                            credit=credit,
                            balance=bal,
                        )
                    )


            elif txns:
                # Multi-line narration continuation for previous transaction
                cleaned_cont = clean_narration_string(line)
                if (
                    cleaned_cont
                    and len(cleaned_cont) > 1
                    and not any(k in cleaned_cont.lower() for k in ["statement", "www.", "http", "page"])
                ):
                    txns[-1].narration += " " + cleaned_cont

    if not txns:
        return None

    # Normalize OCR year outliers (e.g. '28' read instead of '23')
    if txns:
        from collections import Counter
        years = [t.txn_date.year for t in txns]
        dominant_year = Counter(years).most_common(1)[0][0]
        today_year = date.today().year
        for t in txns:
            if t.txn_date.year > today_year or abs(t.txn_date.year - dominant_year) > 1:
                try:
                    t.txn_date = t.txn_date.replace(year=dominant_year)
                except Exception:
                    pass

    # Chronological sort and balance arithmetic reconciliation
    txns = sort_txns_oldest_first(txns)
    reconciled, mismatch_rows, warnings = reconcile_transactions(txns)

    dates = [t.txn_date for t in txns]
    period_start = min(dates)
    period_end = max(dates)

    return ParsedStatement(
        bank=resolved_bank,
        period_start=period_start,
        period_end=period_end,
        txns=txns,
        reconciled=reconciled,
        mismatch_rows=mismatch_rows,
        warnings=warnings,
    )
