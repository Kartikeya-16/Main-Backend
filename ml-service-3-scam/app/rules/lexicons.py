"""
Indian banking whitelist, high-risk TLDs, and Hinglish urgency lexicons for Stage 1.
"""

# Authentic banking, financial, and government domain whitelist in India
INDIAN_LEGIT_DOMAINS = {
    "sbi": ["sbi.co.in", "onlinesbi.sbi", "onlinesbi.com", "bank.sbi"],
    "hdfc": ["hdfcbank.com", "netbanking.hdfcbank.com"],
    "icici": ["icicibank.com", "infinity.icicibank.com"],
    "axis": ["axisbank.com", "retail.axisbank.co.in"],
    "pnb": ["pnbindia.in", "netpnb.com"],
    "kotak": ["kotak.com", "netbanking.kotak.com"],
    "bob": ["bankofbaroda.in", "bobibanking.com"],
    "canara": ["canarabank.com"],
    "union": ["unionbankofindia.co.in"],
    "indusind": ["indusind.com"],
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
    "npci": ["npci.org.in"],
}

# High-risk / unverified TLDs commonly abused in automated phishing kits
HIGH_RISK_TLDS = {
    ".top", ".xyz", ".club", ".site", ".online", ".live", ".vip", ".work",
    ".icu", ".info", ".cc", ".tk", ".ml", ".ga", ".cf", ".gq", ".biz",
    ".download", ".stream", ".link", ".buzz", ".cam", ".click", ".shop",
    ".quest", ".rest", ".monster", ".fit"
}

# Popular URL shorteners & chat redirects
URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "is.gd", "t.co", "cutt.ly", "rb.gy", "rebrand.ly",
    "shorturl.at", "t.me", "wa.me", "chat.whatsapp.com", "ow.ly", "buff.ly", "qr.ae"
}

# Remote screen-sharing / desktop control applications
REMOTE_ACCESS_TOOLS = [
    "anydesk", "teamviewer", "rustdesk", "quicksupport", "airdroid", "zoho assist",
    "screenshare", "screen share", "ultraviewer", "any desk"
]

# Sensitive credentials solicitations
SENSITIVE_CREDENTIAL_KEYWORDS = [
    "otp", "one time password", "pin", "upi pin", "cvv", "atm pin", "password",
    "passcode", "card number", "expiry date", "m-pin", "mpin"
]

# Hinglish & Hindi urgency triggers
HINGLISH_URGENCY_TRIGGERS = [
    "turant", "abhi", "24 ghante", "aaj hi", "block ho jayega", "band ho jayega",
    "suspend hoga", "chalan pending", "kat jayegi", "inam jeeta", "khata band",
    "paisa bhejo", "link pe click karo", "update karein", "turant karein"
]

# Verified Indian Government / Bank sender headers (Alpha sender ID patterns)
VERIFIED_SENDER_PATTERNS = [
    r"^[A-Z]{2}-SBI[A-Z]{2,4}$",
    r"^[A-Z]{2}-HDFC[A-Z]{2,4}$",
    r"^[A-Z]{2}-ICICI[A-Z]{2,4}$",
    r"^[A-Z]{2}-AXIS[A-Z]{2,4}$",
    r"^[A-Z]{2}-KOTAK[A-Z]{2,4}$",
    r"^[A-Z]{2}-PNBSMS$",
    r"^[A-Z]{2}-BOBTXN$",
    r"^[A-Z]{2}-ITDEPT$",
    r"^[A-Z]{2}-UIDAI[A-Z]?$",
    r"^[A-Z]{2}-EPFOHO$",
]
