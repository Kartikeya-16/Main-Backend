import re
import urllib.parse
from typing import Dict, Any, List, Optional, Tuple

# Official banking and institutional domains in India for spoofing verification
AUTHENTIC_DOMAINS = {
    "sbi": ["sbi.co.in", "onlinesbi.sbi", "onlinesbi.com", "bank.sbi"],
    "hdfc": ["hdfcbank.com", "netbanking.hdfcbank.com"],
    "icici": ["icicibank.com", "infinity.icicibank.com"],
    "axis": ["axisbank.com", "retail.axisbank.co.in"],
    "pnb": ["pnbindia.in", "netpnb.com"],
    "kotak": ["kotak.com", "netbanking.kotak.com"],
    "bob": ["bankofbaroda.in", "bobibanking.com"],
    "paytm": ["paytm.com", "paytmbank.com"],
    "phonepe": ["phonepe.com"],
    "gpay": ["pay.google.com", "google.com"],
    "incometax": ["incometax.gov.in", "eportal.incometax.gov.in"],
    "uidai": ["uidai.gov.in", "myaadhaar.uidai.gov.in"],
    "epfo": ["epfindia.gov.in", "unifiedportal-mem.epfindia.gov.in"],
    "rbi": ["rbi.org.in"],
    "sebi": ["sebi.gov.in"],
    "cybercrime": ["cybercrime.gov.in"],
    "trai": ["trai.gov.in"],
}

HIGH_RISK_TLDS = {
    ".top", ".xyz", ".club", ".site", ".online", ".live", ".vip", ".work",
    ".icu", ".info", ".cc", ".tk", ".ml", ".ga", ".cf", ".gq", ".biz",
    ".download", ".stream", ".link", ".buzz", ".cam", ".click"
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "is.gd", "t.co", "cutt.ly", "rb.gy", "rebrand.ly",
    "shorturl.at", "t.me", "wa.me", "chat.whatsapp.com", "ow.ly", "buff.ly"
}

REMOTE_ACCESS_TOOLS = [
    "anydesk", "teamviewer", "rustdesk", "quicksupport", "airdroid", "zoho assist",
    "screenshare", "screen share", "ultraviewer"
]

MALICIOUS_APP_KEYWORDS = [
    ".apk", "download app", "install app", "install apk", "download apk",
    "support.apk", "reward.apk", "kyc.apk", "update.apk", "sbi_reward.apk",
    "yono_update.apk", "loan_instant.apk"
]

ELECTRICITY_BOARDS = [
    "electricity", "power supply", "bijli", "light bill", "msedcl", "uppcl",
    "bescom", "tneb", "wbsedcl", "dhbvn", "uhbvn", "tata power", "adani electricity",
    "torrent power", "kseb", "pspcl", "discom", "power will be disconnected"
]

DIGITAL_ARREST_KEYWORDS = [
    "digital arrest", "mumbai police", "delhi police", "cbi", "ed officer",
    "customs department", "illegal parcel", "drugs in courier", "fedex parcel",
    "skype call", "stay on video call", "arrest warrant", "money laundering case",
    "trai disconnection", "sim blocked by police", "narcotics bureau", "ncb"
]

PART_TIME_JOB_KEYWORDS = [
    "part time job", "youtube like", "hotel review", "google map rating",
    "earn 3000 to 5000", "daily payout", "work from home", "telegram task",
    "prepaid task", "crypto recharge", "vip merchant", "task commission",
    "earn 10000 daily", "easy money"
]

LOTTERY_PRIZE_KEYWORDS = [
    "kbc lottery", "won 25 lakhs", "winner", "prize money", "lucky draw",
    "car winner", "claim your prize", "processing fee for lottery", "kaun banega crorepati"
]

LOAN_FRAUD_KEYWORDS = [
    "pre-approved loan", "loan sanctioned", "instant loan without cibil",
    "no cibil required", "zero interest loan", "pay processing fee to release loan",
    "disbursement fee", "fast cash loan"
]

HINGLISH_SCAM_PATTERNS = [
    r"\baapka\b.*\b(block|band)\b",
    r"\baccount\b.*\b(block|freeze|suspend)\b.*\b(ho jayega|hoga)\b",
    r"\bturant\b.*\b(karein|update|call)\b",
    r"\bpaise\b.*\b(transfer|bhejo|jama)\b",
    r"\binam\b.*\b(jeeta|mila)\b",
    r"\bbijli\b.*\b(kat|disconnect)\b",
    r"\botp\b.*\b(share|batao|bhejo)\b",
    r"\bkyc\b.*\b(expire|update|karo)\b",
    r"\bchalan\b.*\b(bharo|pending)\b",
]


def extract_urls(text: str) -> List[str]:
    """Extract all HTTP/HTTPS links, bare URLs, and IP addresses from text."""
    url_pattern = re.compile(
        r"(https?:\/\/[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(?:com|org|in|net|top|xyz|site|online|live|info|co|cc|club|me|link|app|click|tech|store)\b[^\s]*)",
        re.IGNORECASE
    )
    return [u.rstrip(".,;!?)>\"'") for u in url_pattern.findall(text)]


def extract_upi_ids(text: str) -> List[str]:
    """Extract standard Indian UPI Handles and deep link URIs."""
    upi_deep_links = re.findall(r"upi:\/\/pay\?[^\s]+", text, re.IGNORECASE)
    upi_handles = re.findall(r"\b[a-zA-Z0-9.\-_]{2,40}@[a-zA-Z]{2,20}\b", text)
    return list(dict.fromkeys(upi_deep_links + upi_handles))


def extract_phone_numbers(text: str) -> List[str]:
    """Extract standard Indian phone numbers (10 digits, +91, with spaces/dashes)."""
    phone_pattern = re.compile(r"(?:\+91[\s\-]?)?[6-9]\d{9}\b")
    return list(dict.fromkeys(phone_pattern.findall(text)))


def detect_language(text: str) -> str:
    """Detect if content is in English, Hindi (Devanagari), or Hinglish (Code-mixed)."""
    # Check for Devanagari script range \u0900-\u097F
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    
    hinglish_markers = [
        "aapka", "karo", "karein", "abhi", "turant", "jayega", "hoga", "kare",
        "paise", "bijli", "khata", "bhejo", "bharo", "namaskar", "paisa", "inam"
    ]
    lower_text = text.lower()
    has_hinglish = any(re.search(rf"\b{m}\b", lower_text) for m in hinglish_markers)
    
    if has_devanagari and re.search(r"[a-zA-Z]", text):
        return "Hindi + English (Bilingual)"
    elif has_devanagari:
        return "Hindi (Devanagari)"
    elif has_hinglish:
        return "Hinglish (Hindi written in Latin script)"
    else:
        return "English"


def evaluate_urls(urls: List[str]) -> Tuple[float, List[str], List[str]]:
    """
    Evaluates list of URLs for spoofing, high-risk TLDs, and shorteners.
    Returns (risk_score, warning_signs, threat_entities).
    """
    score = 0.0
    warnings = []
    threats = []

    for raw_url in urls:
        parsed_url = raw_url if raw_url.startswith("http") else "http://" + raw_url
        try:
            parsed = urllib.parse.urlparse(parsed_url)
            netloc = parsed.netloc.lower()
            hostname = netloc.split(":")[0]
        except Exception:
            hostname = raw_url.lower()

        threats.append(raw_url)

        # 1. URL Shortener Risk
        if any(shortener in hostname for shortener in URL_SHORTENERS):
            score += 0.35
            warnings.append(f"Contains shortened/masked redirect link ({hostname}) which hides actual destination.")

        # 2. High-Risk TLDs
        if any(hostname.endswith(tld) for tld in HIGH_RISK_TLDS):
            score += 0.40
            warnings.append(f"Uses high-risk, unverified domain extension ({hostname}) frequently utilized in cyber fraud.")

        # 3. Direct IP Address in URL
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", hostname):
            score += 0.50
            warnings.append(f"Points directly to an untrusted IP address ({hostname}) rather than a secure branded domain.")

        # 4. Brand Spoofing Check
        for brand, valid_domains in AUTHENTIC_DOMAINS.items():
            if brand in hostname:
                is_legit = any(hostname == vd or hostname.endswith("." + vd) for vd in valid_domains)
                if not is_legit:
                    score += 0.60
                    warnings.append(
                        f"Brand Impersonation: Domain '{hostname}' attempts to mimic legitimate '{brand.upper()}' (Official: {valid_domains[0]})."
                    )

        # 5. Suspicious subdomains / keywords inside URL
        suspicious_slugs = ["kyc", "verify", "reward", "login", "bonus", "free", "update", "secure", "apk", "claim"]
        if any(slug in parsed_url.lower() for slug in suspicious_slugs) and not any(hostname.endswith("." + d) for domains in AUTHENTIC_DOMAINS.values() for d in domains):
            score += 0.20
            warnings.append(f"URL path includes deceptive keywords intended to solicit credentials/downloads ({raw_url}).")

    return min(1.0, score), warnings, threats


def analyze_scam_payload(content: str, input_type: str = "text") -> Dict[str, Any]:
    """
    Deep multi-vector analysis of input text, URL, or extracted image content.
    Returns comprehensive forensic report.
    """
    clean_text = content.strip()
    lower_text = clean_text.lower()
    
    warnings: List[str] = []
    threat_indicators: Dict[str, Any] = {
        "extracted_urls": [],
        "extracted_upis": [],
        "extracted_phones": [],
        "spoofed_entities": [],
    }

    base_score = 0.0
    category = "Legitimate / Verified"
    recommendation = "This message appears safe, but always verify unfamiliar senders before sharing details or making payments."
    
    # Extract entities
    urls = extract_urls(clean_text)
    upis = extract_upi_ids(clean_text)
    phones = extract_phone_numbers(clean_text)

    threat_indicators["extracted_urls"] = urls
    threat_indicators["extracted_upis"] = upis
    threat_indicators["extracted_phones"] = phones

    # Evaluate URLs if present
    if urls:
        url_score, url_warnings, _ = evaluate_urls(urls)
        base_score += url_score
        warnings.extend(url_warnings)
        if url_score >= 0.35:
            category = "Phishing / Malicious Domain Spoofing"

    # 1. Fake KYC & Account Block Threat
    is_kyc_fraud = any(k in lower_text for k in ["kyc", "pan card", "aadhaar", "yono", "debit card", "sim block", "account blocked", "account freeze", "suspended"])
    has_urgency = any(k in lower_text for k in ["within 24 hours", "urgently", "immediate", "today only", "turant", "24 ghante", "blocked tonight", "last warning", "expire"])
    
    if is_kyc_fraud and has_urgency:
        base_score += 0.55
        category = "Fake KYC / Account Freeze Scam"
        warnings.append("Creates artificial panic claiming your bank account or SIM will be blocked unless you verify immediately.")
        warnings.append("Demands personal identity or financial updates via unverified SMS/message links.")

    # 2. Electricity / Utility Bill Scam
    if any(k in lower_text for k in ELECTRICITY_BOARDS) and any(k in lower_text for k in ["disconnect", "unpaid", "bill pending", "officer", "helpline", "9:30 pm", "tonight", "power supply"]):
        base_score += 0.65
        category = "Utility Bill Disconnection Threat"
        warnings.append("Electricity bill cutoff scare tactic designed to make you call a scammer's phone number or pay via fake link.")
        warnings.append("State electricity discoms never send sudden disconnection notices via individual WhatsApp or personal mobile numbers.")

    # 3. Digital Arrest & Fake Police / Law Enforcement Scam
    if any(k in lower_text for k in DIGITAL_ARREST_KEYWORDS):
        base_score += 0.85
        category = "Digital Arrest / Law Enforcement Impersonation"
        warnings.append("High-Severity 'Digital Arrest' Threat: Scammers impersonate Police/CBI/Customs claiming illegal courier parcels or arrest warrants.")
        warnings.append("Law enforcement authorities NEVER conduct arrests via Skype/WhatsApp video calls or demand funds transfer for 'verification'.")

    # 4. Part-Time Job / Telegram Task Scam
    if any(k in lower_text for k in PART_TIME_JOB_KEYWORDS):
        base_score += 0.60
        category = "Task / Part-Time Job Scam"
        warnings.append("Offers unrealistic daily income (₹3,000–₹10,000/day) for simple online tasks like liking YouTube videos or writing reviews.")
        warnings.append("Typically funnels victims to Telegram groups before demanding 'security deposits' or 'prepaid tasks' to unlock payouts.")

    # 5. Lottery / KBC / Prize Winner Scam
    if any(k in lower_text for k in LOTTERY_PRIZE_KEYWORDS):
        base_score += 0.70
        category = "Lottery / Prize Reward Fraud"
        warnings.append("Bogus lottery / KBC reward claim designed to elicit 'advance processing charges' or tax deposits.")
        warnings.append("Genuine lotteries and government contests never require winning fees sent to personal UPI IDs.")

    # 6. Remote Screen Sharing / APK Download Scam
    if any(tool in lower_text for tool in REMOTE_ACCESS_TOOLS):
        base_score += 0.75
        category = "Remote Screen Sharing Device Takeover"
        warnings.append(f"Prompts installation of remote access software which grants scammers full control over your smartphone and bank OTPs.")
    
    if any(apk in lower_text for apk in MALICIOUS_APP_KEYWORDS):
        base_score += 0.65
        category = "Malicious APK / Trojan Sideloading"
        warnings.append("Prompts downloading an untrusted Android .APK file outside the official Google Play Store.")

    # 7. UPI & Reverse Payment Fraud (e.g. OLX/Quikr QR trap)
    is_reverse_upi = any(k in lower_text for k in [
        "scan qr to receive", "enter pin to receive", "enter upi pin to receive",
        "scan this qr", "scan qr code", "scan and receive", "qr code to receive",
        "pin enter karke receive", "receive money in your bank account"
    ])
    if is_reverse_upi or (upis and any(k in lower_text for k in ["receive money", "claim refund", "cashback", "processing fee"])):
        base_score += 0.75
        category = "UPI Reverse Payment / QR Code Fraud"
        warnings.append("CRITICAL FRAUD TRAP: Entering your UPI PIN or scanning a QR code ALWAYS DEBITS money from your account, it never credits money.")
        warnings.append("Scammers often pose as buyers on marketplaces (OLX/Quikr) sending fake 'receive payment' QR codes.")

    # 8. Loan Fraud
    if any(k in lower_text for k in LOAN_FRAUD_KEYWORDS) and any(k in lower_text for k in ["processing fee", "file charge", "transfer fee", "deposit advance"]):
        base_score += 0.55
        category = "Fake Loan / Advance Fee Fraud"
        warnings.append("Requires upfront fee/deposit before releasing a loan (RBI-regulated lenders never charge advance fees via UPI).")

    # 9. Hinglish pattern match scoring
    for pattern in HINGLISH_SCAM_PATTERNS:
        if re.search(pattern, lower_text):
            base_score += 0.20
            if "Recognizes Hinglish psychological coercion pattern." not in warnings:
                warnings.append("Contains known Indian conversational phishing phrases and urgency triggers.")
            break

    # Calculate final probability
    probability = round(min(0.99, max(0.04, base_score)), 2)

    # Resolve recommendations and emergency actions based on category & probability
    if probability >= 0.70:
        recommendation = (
            "DO NOT click any links, DO NOT call back on the mentioned phone numbers, and NEVER enter your UPI PIN or share OTPs. "
            "Block the sender immediately. If you have already shared money, contact your bank to freeze transactions and report to National Cyber Crime Helpline 1930."
        )
    elif probability >= 0.40:
        category = category if category != "Legitimate / Verified" else "Unverified / Suspicious Request"
        recommendation = (
            "Exercise caution. Verify the communication independently by directly visiting the organization's official website or official customer care app."
        )
    else:
        category = "Legitimate / Verified"
        warnings = []
        recommendation = "No prominent phishing or financial scam markers were identified. Always remain cautious when sharing sensitive credentials."

    language_detected = detect_language(clean_text)

    return {
        "scam_probability": probability,
        "risk_level": "HIGH" if probability >= 0.70 else ("MEDIUM" if probability >= 0.40 else "SAFE"),
        "category": category,
        "warning_signs": list(dict.fromkeys(warnings)),
        "threat_indicators": threat_indicators,
        "recommendation": recommendation,
        "emergency_action": {
            "helpline": "1930",
            "cybercrime_portal": "https://cybercrime.gov.in",
            "chakshu_portal": "https://sancharsaathi.gov.in/sfc/",
            "report_guidelines": [
                "Call 1930 within the golden hour to freeze fraudulent recipient accounts.",
                "File an official complaint with screenshots at cybercrime.gov.in.",
                "Report suspicious SMS or caller number to the DoT Chakshu portal."
            ]
        },
        "language_detected": language_detected,
    }


def get_active_threat_intel() -> List[Dict[str, Any]]:
    """Returns curated live threat intelligence on prevalent Indian financial scams."""
    return [
        {
            "id": "threat-1",
            "title": "Digital Arrest Scams",
            "severity": "CRITICAL",
            "summary": "Fraudsters pose as CBI / Police / Customs officers via Skype/WhatsApp video calls claiming your Aadhaar or mobile SIM is linked to illegal narcotics courier.",
            "safety_rule": "Indian law enforcement agencies NEVER place citizens under 'Digital Arrest' or demand funds transfer for verification."
        },
        {
            "id": "threat-2",
            "title": "Part-Time Task & YouTube Like Scams",
            "severity": "HIGH",
            "summary": "Victims are lured with ₹50/like payments on WhatsApp, then moved to Telegram and coerced into depositing large sums in 'VIP prepaid tasks'.",
            "safety_rule": "Legitimate organizations never ask job seekers to deposit money to withdraw their own earned salary."
        },
        {
            "id": "threat-3",
            "title": "Electricity Bill Cutoff Threats",
            "severity": "HIGH",
            "summary": "SMS sent from private 10-digit mobile numbers warning electricity will be disconnected tonight at 9:30 PM unless a phone number is dialed.",
            "safety_rule": "Power discoms only send updates via verified SMS headers (e.g. AD-MSEDCL, VK-BESCOM), never standard 10-digit personal numbers."
        },
        {
            "id": "threat-4",
            "title": "QR Code / Reverse Payment Trap",
            "severity": "MEDIUM",
            "summary": "Marketplace buyers (e.g., OLX, Quikr) send QR codes claiming 'Scan to receive your payment'.",
            "safety_rule": "Scanning a QR code or entering a UPI PIN is strictly for SENDING money, NEVER for receiving money."
        }
    ]
