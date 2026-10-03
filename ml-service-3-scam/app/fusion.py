from typing import Dict, Any, List, Optional
from app.models.text_classifier import text_predictor
from app.models.url_classifier import url_predictor
from app.rules.extractor import extract_entities_and_rules


def determine_scam_type(text: str, entities: Dict[str, Any]) -> str:
    """Classifies the specific scam taxonomy category based on detected semantic indicators."""
    lower = text.lower()

    if any(k in lower for k in ["digital arrest", "mumbai police", "delhi police", "cbi", "narcotics", "skype", "fedex parcel", "customs"]):
        return "digital_arrest"
    elif any(k in lower for k in ["electricity", "power supply", "bijli", "msedcl", "bescom", "uppcl", "9:30 pm", "disconnect"]):
        return "utility_cutoff"
    elif entities.get("is_reverse_upi") or any(k in lower for k in ["scan qr to receive", "enter pin to receive", "qr code"]):
        return "upi_reverse_payment"
    elif any(k in lower for k in ["kyc", "pan card", "yono", "aadhaar", "block", "freeze", "deactivated"]):
        return "kyc_update"
    elif any(k in lower for k in ["youtube like", "part time job", "hotel review", "telegram task", "prepaid task", "vip task"]):
        return "part_time_job"
    elif any(k in lower for k in ["kbc", "lottery", "prize", "winner", "won 25"]):
        return "lottery_prize"
    elif any(k in lower for k in ["anydesk", "teamviewer", "rustdesk", "quicksupport"]):
        return "remote_access_trojan"
    elif any(k in lower for k in ["loan approved", "instant loan", "processing fee for loan", "cibil"]):
        return "loan_fraud"
    else:
        return "phishing_social_engineering"


def generate_advice(scam_type: str, score: float) -> str:
    """Generates official, actionable advice referencing Indian cybercrime portals and 1930 helpline."""
    if score < 0.35:
        return "This message appears safe. Always verify senders before sharing personal information or transferring funds."

    if scam_type == "digital_arrest":
        return "CRITICAL: Disconnect immediately. Indian Police and CBI NEVER conduct arrests via video call or demand verification funds. Report immediately to 1930 or cybercrime.gov.in."
    elif scam_type == "upi_reverse_payment":
        return "CRITICAL: Do NOT scan the QR code or enter your UPI PIN. Entering your PIN ALWAYS debits money from your account. Report suspected fraud numbers to the DoT Chakshu portal (sancharsaathi.gov.in) or 1930."
    elif scam_type == "utility_cutoff":
        return "Do NOT call the personal mobile number. Power discoms never send sudden disconnection warnings via personal 10-digit numbers. Check bill status on your official electricity portal and report SMS to Chakshu / 1930."
    elif scam_type == "kyc_update":
        return "Do NOT click the link or share OTP/Aadhaar/PAN details. Banks never update KYC via SMS links. Log in only through official bank apps and report suspicious links to DoT Chakshu (sancharsaathi.gov.in) or call 1930."
    elif scam_type == "part_time_job":
        return "Refuse prepaid recharge tasks. Genuine companies never demand money from job seekers to release earned wages. Block the Telegram channel and report to cybercrime.gov.in or 1930."
    elif scam_type == "lottery_prize":
        return "Do NOT pay processing fees. Genuine lotteries never demand advance tax deposits sent to personal UPI IDs. Report to cybercrime.gov.in or 1930."
    else:
        return "Do not click unverified links or share sensitive information. Report suspicious SMS/caller numbers at sancharsaathi.gov.in (Chakshu) or call 1930 if financial loss occurred."


def fuse_risk(text: str, sender: Optional[str] = None) -> Dict[str, Any]:
    """
    Stage 4: Risk Fusion & Reason Generation
    - Runs Stage 1: Entity & Rule Extractor
    - Runs Stage 2: Text ML Classifier
    - Runs Stage 3: Lexical URL Phishing Model for all detected links
    - Applies Rule Floors and Caps
    - Generates Explainable Red Flags and Official Advice
    """
    entities = extract_entities_and_rules(text, sender)
    reasons: List[str] = []

    # Stage 2: Text ML Classification
    text_pred_class, text_scam_prob, prob_dict = text_predictor.predict(text)

    # Stage 3: URL Phishing Evaluation
    url_results: List[Dict[str, Any]] = []
    max_url_prob = 0.0
    for u in entities["urls"]:
        u_eval = url_predictor.evaluate_url(u)
        url_results.append(u_eval)
        max_url_prob = max(max_url_prob, u_eval["phishing_probability"])
        reasons.extend(u_eval["reasons"])

    # Base Fusion Score
    if entities["urls"]:
        fused_score = max(text_scam_prob, max_url_prob)
    else:
        fused_score = text_scam_prob

    # Rule Floors & Boosts (Stage 4 Overrides)
    if entities["has_otp_request"]:
        fused_score = max(fused_score, 0.82)
        reasons.append("Requests sensitive authentication credentials (OTP / PIN / Password).")

    if entities["is_reverse_upi"]:
        fused_score = max(fused_score, 0.85)
        reasons.append("Deceptive UPI / QR reverse payment trap: Claims scanning QR or entering PIN will credit money.")

    if any(u["is_spoofed_brand"] for u in url_results):
        fused_score = max(fused_score, 0.92)

    if entities["suspicious_apks"]:
        fused_score = max(fused_score, 0.78)
        reasons.append(f"Prompts downloading an untrusted Android APK file ({', '.join(entities['suspicious_apks'])}).")

    if entities["has_remote_tool"]:
        fused_score = max(fused_score, 0.80)
        reasons.append("Prompts installation of remote access screen-sharing software (e.g. AnyDesk, TeamViewer).")

    if entities["has_urgency"] and fused_score > 0.40:
        reasons.append("Uses coercive urgency triggers (e.g. 'account blocked within 24 hours', 'turant karein').")

    # Rule Caps
    if entities["is_sender_verified"] and not entities["urls"] and not entities["has_otp_request"]:
        fused_score = min(fused_score, 0.25)

    if text_pred_class == "promo" and fused_score < 0.60:
        fused_score = min(fused_score, 0.30)
        reasons.append("Identified as legitimate promotional / marketing communication.")

    final_score = round(min(0.99, max(0.04, fused_score)), 2)
    risk_level = "scam" if final_score >= 0.70 else ("suspicious" if final_score >= 0.35 else "safe")

    scam_type = determine_scam_type(text, entities) if risk_level != "safe" else "legit"
    advice = generate_advice(scam_type, final_score)

    return {
        "risk_level": risk_level,
        "score": final_score,
        "scam_type": scam_type,
        "reasons": list(dict.fromkeys(reasons)),
        "urls": url_results,
        "extracted_entities": {
            "urls": entities["urls"],
            "upis": entities["upis"],
            "phones": entities["phones"],
            "amounts": entities["amounts"],
            "suspicious_apks": entities["suspicious_apks"],
        },
        "advice": advice,
        "language_detected": entities["language"],
    }
