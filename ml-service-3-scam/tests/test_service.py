"""
Pytest test suite for ml-service-3-scam hybrid pipeline and API endpoints.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.main import app
from app.rules.extractor import extract_entities_and_rules, check_brand_spoofing
from app.models.text_classifier import text_predictor
from app.models.url_classifier import url_predictor
from app.fusion import fuse_risk

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ml-service-3-scam"


def test_rule_extractor_entities():
    text = "Update KYC at http://bit.ly/sbi-kyc or pay Rs 5,000 to kbc-verify@ybl. Call 9876543210 immediately."
    entities = extract_entities_and_rules(text)
    assert len(entities["urls"]) > 0
    assert "http://bit.ly/sbi-kyc" in entities["urls"]
    assert "kbc-verify@ybl" in entities["upis"]
    assert "9876543210" in entities["phones"]
    assert entities["has_urgency"] is True


def test_brand_spoofing_check():
    # Phishing lookalike domain
    is_spoofed, brand, official = check_brand_spoofing("http://sbi-kyc-verification.top/update")
    assert is_spoofed is True
    assert brand == "SBI"
    assert "sbi" in official

    # Authentic domain
    is_legit, _, _ = check_brand_spoofing("https://www.onlinesbi.sbi/login")
    assert is_legit is False


def test_text_classifier_predictions():
    scam_text = "Dear Customer, your bank account will be blocked within 24 hours. Update PAN immediately."
    pred_class, prob, probs_dict = text_predictor.predict(scam_text)
    assert pred_class == "scam"
    assert prob >= 0.70

    promo_text = "Get flat 50% off on your next pizza order on Swiggy with coupon PIZZA50!"
    pred_class_promo, prob_promo, _ = text_predictor.predict(promo_text)
    assert pred_class_promo == "promo"

    legit_text = "Your A/C ending 4321 credited with INR 75,000.00 by NEFT-Salary. - HDFC Bank"
    pred_class_legit, prob_legit, _ = text_predictor.predict(legit_text)
    assert pred_class_legit == "legit"


def test_url_classifier():
    phish_res = url_predictor.evaluate_url("http://hdfc-netbanking.xyz/login.php")
    assert phish_res["phishing_probability"] >= 0.70
    assert phish_res["is_spoofed_brand"] is True

    legit_res = url_predictor.evaluate_url("https://netbanking.hdfcbank.com/netbanking/")
    assert legit_res["phishing_probability"] < 0.35


def test_hard_negatives_safe_score():
    # A genuine OTP message with "Do not share OTP" must stay in the safe zone
    otp_text = "849201 is your one-time password (OTP) for login to your HDFC account. Valid for 10 mins. Do not share OTP with anyone."
    result = fuse_risk(otp_text, sender="VM-HDFCBK")
    assert result["risk_level"] == "safe"
    assert result["score"] < 0.35


def test_full_analyze_endpoint_scam():
    payload = {
        "text": "Dear SBI Customer, aapka YONO account block ho jayega within 24 hours. Urgently update your PAN/Aadhaar details here: http://bit.ly/sbi-kyc-update-live"
    }
    response = client.post("/scam/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "scam"
    assert data["score"] >= 0.85
    assert data["scam_type"] == "kyc_update"
    assert len(data["reasons"]) > 0
    assert "1930" in data["advice"] or "Chakshu" in data["advice"] or "sancharsaathi" in data["advice"]
