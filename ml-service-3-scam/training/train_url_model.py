"""
Trains Lexical URL Phishing Model on 25 Lexical Features:
- Length/structure features (length, path depth, subdomains, special chars)
- Statistical features (digit ratio, Shannon entropy)
- Host features (IP address, HTTPS, shortener, high-risk TLD, brand similarity)
- Trains Random Forest Classifier and saves to artifacts/url_phish_model.joblib.
"""
import os
import math
import re
import urllib.parse
from typing import List, Dict, Any
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

from dataset_builder import generate_url_dataset
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.rules.lexicons import INDIAN_LEGIT_DOMAINS, HIGH_RISK_TLDS, URL_SHORTENERS

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(BASE_DIR, "app", "data", "url_phishing_dataset.csv")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)
MODEL_OUT = os.path.join(ARTIFACTS_DIR, "url_phish_model.joblib")


def calculate_entropy(text: str) -> float:
    """Calculates Shannon entropy of string."""
    if not text:
        return 0.0
    prob = [float(text.count(c)) / len(text) for c in dict.fromkeys(list(text))]
    return -sum([p * math.log(p) / math.log(2.0) for p in prob if p > 0])


def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes Levenshtein edit distance."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def extract_url_features(raw_url: str) -> List[float]:
    """
    Extracts 25 pure lexical features from a raw URL string without network calls.
    """
    url_str = raw_url.strip()
    parsed_url = url_str if url_str.startswith("http") else "http://" + url_str
    try:
        parsed = urllib.parse.urlparse(parsed_url)
        netloc = parsed.netloc.lower().split(":")[0]
        path = parsed.path.lower()
        query = parsed.query.lower()
    except Exception:
        netloc = url_str.lower()
        path = ""
        query = ""

    # 1-3. Lengths
    url_len = len(url_str)
    domain_len = len(netloc)
    path_len = len(path)

    # 4-9. Special Character Counts
    dot_count = url_str.count(".")
    hyphen_count = url_str.count("-")
    at_count = url_str.count("@")
    slash_count = url_str.count("/")
    question_count = url_str.count("?")
    equal_count = url_str.count("=")

    # 10. Subdomains count
    subdomains_count = max(0, netloc.count(".") - 1)

    # 11-12. Domain Digit & Special Character ratios
    digits_in_domain = sum(c.isdigit() for c in netloc)
    digit_ratio_domain = digits_in_domain / max(1, domain_len)
    special_chars_domain = sum(not c.isalnum() for c in netloc)
    special_ratio_domain = special_chars_domain / max(1, domain_len)

    # 13. Shannon Entropy of Domain
    domain_entropy = calculate_entropy(netloc)

    # 14. Is IP Address
    is_ip = 1.0 if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", netloc) else 0.0

    # 15. Is HTTPS
    is_https = 1.0 if url_str.lower().startswith("https") else 0.0

    # 16. Is URL Shortener
    is_shortener = 1.0 if any(s in netloc for s in URL_SHORTENERS) else 0.0

    # 17. High Risk TLD
    is_high_risk_tld = 1.0 if any(netloc.endswith(tld) for tld in HIGH_RISK_TLDS) else 0.0

    # 18. Is Verified Indian Institutional Domain (.gov.in, .bank.in, .nic.in)
    is_gov_or_bank_in = 1.0 if any(netloc.endswith(ext) for ext in [".gov.in", ".nic.in", ".bank.in", ".ac.in", ".res.in"]) else 0.0

    # 19. Suspicious keywords in path/query (login, kyc, verify, apk, reward, update, auth)
    suspicious_words = ["login", "kyc", "verify", "apk", "reward", "update", "auth", "free", "claim", "secure", "bank"]
    keyword_count = sum(1 for w in suspicious_words if w in (path + query))

    # 20. Brand lookalike distance
    # Measure minimum distance to known Indian banking brand names
    brand_distances = [
        levenshtein_distance(netloc.replace(".", "").replace("-", ""), brand)
        for brand in INDIAN_LEGIT_DOMAINS.keys()
    ]
    min_brand_dist = min(brand_distances) if brand_distances else 10.0

    # 21. Brand in subdomain or path while registered domain is different
    has_brand_in_subpath = 0.0
    for brand in INDIAN_LEGIT_DOMAINS.keys():
        if brand in (path + query) or (brand in netloc and not any(netloc.endswith(d) for d in INDIAN_LEGIT_DOMAINS[brand])):
            has_brand_in_subpath = 1.0
            break

    # 22. Vowel to consonant ratio in domain
    vowels = sum(c in "aeiou" for c in netloc)
    consonants = sum(c.isalpha() and c not in "aeiou" for c in netloc)
    vowel_ratio = vowels / max(1, consonants)

    # 23. Port specified in URL
    has_port = 1.0 if (":" in parsed.netloc and not parsed.netloc.endswith(":80") and not parsed.netloc.endswith(":443")) else 0.0

    # 24. Number of query parameters
    query_params_count = len(urllib.parse.parse_qs(query))

    # 25. Excessive hyphenation in domain (common in phishing like hdfc-net-banking-update-pan.top)
    excessive_hyphens = 1.0 if netloc.count("-") >= 2 else 0.0

    return [
        float(url_len),
        float(domain_len),
        float(path_len),
        float(dot_count),
        float(hyphen_count),
        float(at_count),
        float(slash_count),
        float(question_count),
        float(equal_count),
        float(subdomains_count),
        digit_ratio_domain,
        special_ratio_domain,
        domain_entropy,
        is_ip,
        is_https,
        is_shortener,
        is_high_risk_tld,
        is_gov_or_bank_in,
        float(keyword_count),
        float(min_brand_dist),
        has_brand_in_subpath,
        vowel_ratio,
        has_port,
        float(query_params_count),
        excessive_hyphens
    ]


def train_url_classifier():
    if not os.path.exists(DATA_PATH):
        generate_url_dataset()

    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} samples from {DATA_PATH}. Class distribution:")
    print(df["label"].value_counts())

    X_features = np.array([extract_url_features(u) for u in df["url"]])
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X_features, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        random_state=42,
        class_weight="balanced"
    )

    print("\nTraining Lexical URL Phishing Classifier...")
    clf.fit(X_train, y_train)

    y_pred = clf.predict(X_test)
    y_prob = clf.predict_proba(X_test)[:, 1]

    print("\n=== CLASSIFICATION REPORT (URL Phishing Model) ===")
    print(classification_report(y_test, y_pred, digits=4))
    print(f"ROC-AUC Score: {roc_auc_score(y_test, y_prob):.4f}")

    joblib.dump(clf, MODEL_OUT)
    print(f"\nModel successfully saved to: {MODEL_OUT}")
    return clf


if __name__ == "__main__":
    train_url_classifier()
