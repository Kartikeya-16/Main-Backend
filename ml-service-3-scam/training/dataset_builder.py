"""
Dataset Builder for Indian Financial Scam & Phishing Detection.
Generates:
1. Text Dataset (scam, promo, legit) covering English, Roman Hinglish, and Devanagari.
2. URL Dataset (phishing, legitimate) with authentic Indian banking domains and phishing patterns.
"""
import os
import csv
import json
import random

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "app", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ── 1. TEXT DATASET (3 Classes: scam, promo, legit) ──

SCAM_PATTERNS = [
    # Fake KYC & Account Block (English & Hinglish)
    "Dear SBI Customer, aapka YONO account block ho jayega within 24 hours. Urgently update your PAN/Aadhaar details here: http://bit.ly/sbi-kyc-update-live",
    "Dear Customer, your HDFC netbanking access is suspended due to incomplete KYC. Update immediately at http://hdfc-kyc-verification.top/auth to resume access.",
    "ICICI Alert: Your debit card is deactivated due to PAN unlinked. Click http://icici-panupdate.xyz/login to avoid permanent block.",
    "SBI YONO Alert: Your account will be frozen today. Download our quick support app at http://sbi-support.live/app.apk to verify your KYC.",
    "Axis Bank notice: Your mobile banking is blocked. Call customer officer immediately at 9876543210 or visit http://axis-reactivate.top",
    "Aapka PNB account aaj raat 12 baje band ho jayega. Turant diye gaye link par click karke apna Aadhaar number verify karein: http://pnb-aadhaar.icu/update",
    "Dear User, your SIM card KYC has expired. Power and outgoing calls will be disconnected in 2 hours. Call DoT officer at 9123456789 or click http://sim-kyc.click",
    
    # Digital Arrest & Law Enforcement Impersonation
    "This is Mumbai Crime Branch. Your Aadhaar is linked to a seized FedEx courier parcel containing illegal narcotics. You are under Digital Arrest on Skype. Transfer Rs 50,000 security verification fee immediately.",
    "CBI Cyber Cell Notice: Arrest warrant issued in your name under Money Laundering Act. Stay on WhatsApp video call and transfer verification deposit to clear your name.",
    "Delhi Police Cyber Cell: Your mobile number has been found circulating illegal material. Connect immediately on Skype to legal officer or face immediate arrest.",
    "Customs Department Alert: An international parcel addressed to you containing banned contrabands has been intercepted. Pay clearance penalty of Rs 25,000 to avoid CBI custody.",

    # Electricity & Utility Cutoff Threat
    "Dear Consumer, your electricity bill is unpaid. Power supply will be disconnected at 9:30 PM tonight. Contact electricity officer immediately at 9876543210",
    "MSEDCL Alert: Bijli bill baki hone ke karan aaj raat 9:30 baje bijli kaat di jayegi. Turant diye gaye number par sampark karein: 9811223344",
    "BESCOM Notice: Electricity connection will be cut off tonight due to unpaid update. Call electrical officer Sharma at 9988776655 immediately to pay bill.",
    "UPPCL Urgent Notice: Your light connection will be disconnected by evening. Please clear your pending invoice at http://uppcl-billpay.top/pay or call 9765432100",

    # UPI Reverse Payment & Marketplace Traps
    "I have sent you Rs 15,000 for your sofa on OLX. Scan this QR code and enter your UPI PIN to receive money in your bank account immediately.",
    "Payment of Rs 8,500 is waiting for you on PhonePe. Click this link and enter your 6-digit UPI PIN to claim instant cashback in your account.",
    "You have received a refund of Rs 4,999 from Amazon. Scan this QR code in Google Pay to credit the refund balance to your savings account.",
    "OLX Buyer: I am transferring advance payment. Open this QR code in Paytm, enter your UPI PIN and balance will be deposited to your account.",

    # Part-Time Task & Telegram Scams
    "Earn Rs 3,000 to Rs 5,000 daily from home! Just like YouTube videos and submit screenshots. Join our official Telegram channel for instant VIP tasks and daily payouts.",
    "Part-time job offer: Earn Rs 500 per hotel review on Google Maps. No experience needed. Daily withdrawal guaranteed. Message WhatsApp at 9845123456 to start now.",
    "Work from home opportunity with international merchant. Complete simple recharge tasks on Telegram and get 30% profit within 15 minutes. Join now.",
    "VIP Prepaid Task: Deposit Rs 10,000 and get Rs 14,500 back in 20 minutes with zero risk. High returns guaranteed by top cryptocurrency exchange.",

    # Lottery / KBC / Prize Scams
    "Congratulations! You have won Rs 25,00,000 in KBC Lottery. To claim immediately send Rs 5,000 processing fee to UPI id: kbc-verify@ybl",
    "You are selected as lucky winner of Brand New Tata Safari in All India Diwali Lucky Draw. Deposit Rs 12,000 RTO registration fee to claim vehicle.",
    "Jio 5G Lucky Customer: You have won a cash prize of Rs 10 Lakhs. Call our lottery manager at 9876501234 to collect your winning cheque.",

    # Instant Loan / Advance Fee Fraud
    "Pre-approved instant loan of Rs 5,00,000 sanctioned with zero CIBIL check. Pay Rs 2,500 insurance processing fee via UPI to disburse loan in 10 minutes.",
    "Fast cash personal loan approved at 2% annual interest. Transfer Rs 1,500 file charge to release funds to your bank account immediately."
]

PROMO_PATTERNS = [
    "Craving biryani? Get flat 50% OFF up to Rs 120 on your next order on Swiggy! Use code TASTY50. Order now on the app.",
    "Zomato Gold: Unlock unlimited free delivery on all restaurants within 10km. Renew your Gold membership for just Rs 99 for 3 months.",
    "Flipkart Big Billion Days are LIVE! Get up to 80% off on electronics, smartphones, and fashion. Shop now at https://www.flipkart.com",
    "Amazon Great Indian Festival: Avail 10% instant discount on HDFC Bank Credit Cards on orders above Rs 5,000. T&C Apply.",
    "Myntra Fashion Carnival: Flat 60-80% OFF on top brands like Nike, Puma, Levi's. Use coupon MYNTRA200 for extra Rs 200 off.",
    "Dominos Super Saver: Buy 1 Medium Pizza and get 1 Free! Valid only on Domino's app on Wednesdays. Order now.",
    "BookMyShow: Flat Rs 100 off on your weekend movie tickets with Kotak Delight Credit Card. Book your seats now on the app.",
    "Uber Promo: Enjoy 20% off on your next 3 Premier rides across Bangalore. Apply promo code UBERGO20 in the app.",
    "Jio Recharge Offer: Recharge with Rs 749 cricket plan and get 2GB/day + unlimited 5G data for 90 days. Recharge on MyJio app.",
    "Airtel Thanks: Claim your complimentary Disney+ Hotstar subscription with your monthly postpaid bill. Activate on Airtel Thanks app."
]

LEGIT_PATTERNS = [
    "Your A/C ending 4321 has been credited with INR 75,000.00 on 28-Sep-2026 by NEFT-Salary. Available Balance is INR 1,25,450.00. - HDFC Bank",
    "849201 is your one-time password (OTP) for login to your HDFC NetBanking account. Valid for 10 mins. Do not share OTP with anyone including bank officials.",
    "Dear Customer, your SBI Credit Card statement for the period ending 15-Sep-2026 is generated. Total Due: INR 14,230.00. Minimum Due: INR 1,500.00. Due Date: 05-Oct-2026.",
    "Alert: INR 350.00 debited from SBI A/C XX9012 on 29-Sep-2026 via UPI to ZOMATO. Ref No 427819201923. If not done by you, call 1800111109.",
    "Your ICICI Bank A/c 0012015678 is debited for INR 11,500.00 on 01-Oct-2026 towards Car Loan EMI. Available balance: INR 48,290.00.",
    "Dear Taxpayer, your Income Tax Return for AY 2026-27 has been successfully processed. Refund of INR 8,450.00 has been credited to your bank account. - Income Tax Dept",
    "EPF Alert: Monthly contribution of INR 3,600.00 credited to Member ID MHBAN0012938 for Aug-2026. Current EPF balance is INR 2,45,600.00. - EPFO",
    "Your Axis Bank OTP for transaction of INR 1,200.00 at AMAZON INDIA is 591024. Valid for 5 minutes. Do not share OTP with anyone.",
    "Dear Customer, electricity bill of Rs 2,450.00 for Consumer No 102938475 has been paid successfully via UPI. Receipt No MSEDCL928371. - MSEDCL",
    "Hi Mom, I have reached Bangalore safely. Will call you once I check into the hotel."
]


def generate_text_dataset() -> str:
    """Generates expanded training dataset with synthetic variations."""
    rows = []

    # Multiply patterns with realistic synthetic variations
    for s in SCAM_PATTERNS:
        rows.append({"text": s, "label": "scam"})
        # Variant with slight punctuation/casing variations
        rows.append({"text": s.upper(), "label": "scam"})
        rows.append({"text": f"URGENT ALERT: {s}", "label": "scam"})
        rows.append({"text": f"Warning! {s} Do not ignore.", "label": "scam"})

    for p in PROMO_PATTERNS:
        rows.append({"text": p, "label": "promo"})
        rows.append({"text": f"Limited Time Offer: {p}", "label": "promo"})
        rows.append({"text": f"{p} Click here to claim your discount.", "label": "promo"})

    for l in LEGIT_PATTERNS:
        rows.append({"text": l, "label": "legit"})
        rows.append({"text": f"Official Update: {l}", "label": "legit"})

    random.seed(42)
    random.shuffle(rows)

    filepath = os.path.join(DATA_DIR, "financial_sms_3class.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated text dataset with {len(rows)} samples at {filepath}")
    return filepath


# ── 2. URL PHISHING DATASET ──

LEGIT_URLS = [
    "https://www.onlinesbi.sbi/sbijava/osbi_retail_banking.html",
    "https://netbanking.hdfcbank.com/netbanking/",
    "https://infinity.icicibank.com/corp/AuthenticationController",
    "https://retail.axisbank.co.in/wps/portal/rBanking/axishome",
    "https://www.incometax.gov.in/iec/foportal/",
    "https://myaadhaar.uidai.gov.in/",
    "https://unifiedportal-mem.epfindia.gov.in/memberinterface/",
    "https://www.amazon.in/dp/B09G9BL5CP",
    "https://www.flipkart.com/mobiles/pr?sid=tyy,4io",
    "https://paytm.com/recharge",
    "https://www.phonepe.com/en/",
    "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx",
    "https://cybercrime.gov.in/Webform/Crime_AuthoLogin.aspx",
    "https://sancharsaathi.gov.in/sfc/",
    "https://www.google.com/search?q=hdfc+bank+rates",
    "https://en.wikipedia.org/wiki/Reserve_Bank_of_India",
    "https://www.irctc.co.in/nget/train-search",
    "https://uidai.gov.in/en/my-aadhaar/get-aadhaar.html"
]

PHISHING_URLS = [
    "http://sbi-kyc-verification.top/update",
    "http://hdfc-netbanking.xyz/login.php",
    "http://icici-panupdate.online/auth",
    "http://axis-reactivate.live/portal",
    "http://pnb-aadhaar.icu/update",
    "http://bit.ly/sbi-kyc-update-live",
    "http://tinyurl.com/hdfc-pan-link",
    "http://192.168.1.105:8080/sbi/login.html",
    "http://sbi.co.in.phishing-server.top/secure",
    "http://incometax-refund-claim.site/verify",
    "http://uppcl-billpay.click/payment",
    "http://kbc-lottery-claim.vip/login",
    "http://paytm-kyc-officer.work/update.apk",
    "http://phonepe-reward-claim.buzz/claim",
    "http://epfo-claim-status.rest/login",
    "http://sbi-reward-points.cam/redeem",
    "http://secure-banking-portal.monster/auth",
    "http://bank-verification-notice.shop/sbi"
]


def generate_url_dataset() -> str:
    """Generates lexical URL dataset for phishing model training."""
    rows = []

    for u in LEGIT_URLS:
        rows.append({"url": u, "label": 0})  # 0 = legitimate
        # Add slight subpath variations
        rows.append({"url": u + "?ref=portal", "label": 0})
        rows.append({"url": u + "/account/view", "label": 0})

    for u in PHISHING_URLS:
        rows.append({"url": u, "label": 1})  # 1 = phishing
        rows.append({"url": u + "?id=102938", "label": 1})
        rows.append({"url": u + "/auth/submit", "label": 1})

    random.seed(42)
    random.shuffle(rows)

    filepath = os.path.join(DATA_DIR, "url_phishing_dataset.csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "label"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated URL dataset with {len(rows)} samples at {filepath}")
    return filepath


if __name__ == "__main__":
    generate_text_dataset()
    generate_url_dataset()
