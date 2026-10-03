import re
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional
from app.rules.lexicons import (
    INDIAN_LEGIT_DOMAINS,
    HIGH_RISK_TLDS,
    URL_SHORTENERS,
    REMOTE_ACCESS_TOOLS,
    SENSITIVE_CREDENTIAL_KEYWORDS,
    HINGLISH_URGENCY_TRIGGERS,
    VERIFIED_SENDER_PATTERNS,
)


def extract_urls(text: str) -> List[str]:
    """Extracts all URLs, HTTP/HTTPS links, and bare domains from text."""
    url_pattern = re.compile(
        r"(https?:\/\/[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(?:com|org|in|net|top|xyz|site|online|live|info|co|cc|club|me|link|app|click|tech|store|shop|vip|work|icu)\b[^\s]*)",
        re.IGNORECASE
    )
    matches = url_pattern.findall(text)
    return [u.rstrip(".,;!?)>\"'") for u in matches]


def extract_upi_ids(text: str) -> List[str]:
    """Extracts standard Indian UPI Handles and deep link URIs."""
    upi_deep_links = re.findall(r"upi:\/\/pay\?[^\s]+", text, re.IGNORECASE)
    upi_handles = re.findall(r"\b[a-zA-Z0-9.\-_]{2,40}@[a-zA-Z]{2,20}\b", text)
    return list(dict.fromkeys(upi_deep_links + upi_handles))


def extract_phone_numbers(text: str) -> List[str]:
    """Extracts 10-digit Indian phone numbers."""
    phone_pattern = re.compile(r"(?:\+91[\s\-]?)?[6-9]\d{9}\b")
    return list(dict.fromkeys(phone_pattern.findall(text)))


def extract_amounts(text: str) -> List[str]:
    """Extracts currency mentions in INR (Rs, INR, ₹, Lakhs, Crores)."""
    amount_pattern = re.compile(r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{2})?(?:\s*(?:Lakhs?|Crores?|L|Cr))?", re.IGNORECASE)
    return list(dict.fromkeys(amount_pattern.findall(text)))


def detect_language(text: str) -> str:
    """Detects if text is English, Devanagari Hindi, or Roman Hinglish."""
    has_devanagari = bool(re.search(r"[\u0900-\u097F]", text))
    
    hinglish_markers = [
        "aapka", "karo", "karein", "abhi", "turant", "jayega", "hoga", "kare",
        "paise", "bijli", "khata", "bhejo", "bharo", "namaskar", "paisa", "inam",
        "chalan", "shikayat", "sampark"
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


def check_brand_spoofing(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Checks if a URL contains an authentic Indian brand name in its hostname/path
    without actually belonging to the authentic domain list.
    Returns (is_spoofed, target_brand, official_domain).
    """
    parsed_url = url if url.startswith("http") else "http://" + url
    try:
        parsed = urllib.parse.urlparse(parsed_url)
        hostname = (parsed.netloc.lower().split(":")[0])
    except Exception:
        hostname = url.lower()

    for brand, valid_domains in INDIAN_LEGIT_DOMAINS.items():
        if brand in hostname:
            is_authentic = any(hostname == vd or hostname.endswith("." + vd) for vd in valid_domains)
            if not is_authentic:
                return True, brand.upper(), valid_domains[0]

    return False, None, None


def check_verified_sender(sender: Optional[str]) -> bool:
    """Checks if the SMS sender header matches a verified bank/govt format."""
    if not sender:
        return False
    clean_sender = sender.strip().upper()
    return any(re.match(p, clean_sender) for p in VERIFIED_SENDER_PATTERNS)


def extract_entities_and_rules(text: str, sender: Optional[str] = None) -> Dict[str, Any]:
    """
    Stage 1: Extracts structured entities and forensic heuristic flags.
    """
    lower_text = text.lower()

    urls = extract_urls(text)
    upis = extract_upi_ids(text)
    phones = extract_phone_numbers(text)
    amounts = extract_amounts(text)
    
    suspicious_apks = [w for w in re.findall(r"\b[\w-]+\.apk\b", lower_text)]

    # Rule flags
    has_otp_disclaimer = any(d in lower_text for d in [
        "do not share", "never share", "don't share", "do not disclose", "never disclose",
        "kisi se share na kare", "kisi ko na bataye", "na bataye", "share mat kare", "not share"
    ])

    has_otp_request = False
    if not has_otp_disclaimer:
        has_otp_request = any(k in lower_text for k in SENSITIVE_CREDENTIAL_KEYWORDS) and any(
            a in lower_text for a in ["share", "enter", "send", "give", "verify", "batao", "bhejo", "input"]
        )

    has_urgency = any(u in lower_text for u in HINGLISH_URGENCY_TRIGGERS) or any(
        e in lower_text for e in ["within 24 hours", "immediately", "urgent", "last warning", "today only", "account blocked", "freeze"]
    )

    has_remote_tool = any(tool in lower_text for tool in REMOTE_ACCESS_TOOLS)
    
    is_reverse_upi = any(k in lower_text for k in [
        "scan qr to receive", "enter pin to receive", "enter upi pin to receive",
        "scan this qr", "scan qr code", "scan and receive", "qr code to receive",
        "pin enter karke receive", "receive money in your bank account"
    ])

    is_sender_verified = check_verified_sender(sender)

    return {
        "urls": urls,
        "upis": upis,
        "phones": phones,
        "amounts": amounts,
        "suspicious_apks": suspicious_apks,
        "has_otp_request": has_otp_request,
        "has_urgency": has_urgency,
        "has_remote_tool": has_remote_tool,
        "is_reverse_upi": is_reverse_upi,
        "is_sender_verified": is_sender_verified,
        "language": detect_language(text),
    }
