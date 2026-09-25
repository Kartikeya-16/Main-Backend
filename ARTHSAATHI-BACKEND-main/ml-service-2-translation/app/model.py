import os
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Clean empty HF_HOME from environment to avoid Hugging Face using an empty string as a cache directory
if os.environ.get("HF_HOME") == "":
    os.environ.pop("HF_HOME", None)

try:
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    from IndicTransToolkit import IndicProcessor
    from huggingface_hub import login
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    AutoModelForSeq2SeqLM = None
    AutoTokenizer = None
    IndicProcessor = None
    login = None
    TORCH_AVAILABLE = False

from app.languages import route_translation_model, LANGUAGES, MIRROR_MODELS
from app.cache import translation_cache


# Globally authenticate with Hugging Face Hub if token is available
hf_token = os.getenv("HF_TOKEN")
if hf_token and login is not None:
    try:
        login(token=hf_token)
    except Exception as e:
        print(f"Warning: Failed to authenticate with Hugging Face token globally: {e}")

# Fallback financial & vernacular dictionary for testing without 2GB+ model download
SAMPLE_TRANSLATIONS = {
    "hin_Deva": {
        "Hello": "नमस्ते",
        "Welcome to ArthSaathi": "अर्थसाथी में आपका स्वागत है",
        "Your financial security is our priority": "आपकी वित्तीय सुरक्षा हमारी प्राथमिकता है",
        "Financial Twin": "वित्तीय ट्विन",
        "Smart Planner": "स्मार्ट योजनाकार",
        "Scam Shield": "धोखाधड़ी ढाल (स्कैम शील्ड)",
        "Government Schemes": "सरकारी योजनाएं",
        "High Scam Risk": "उच्च धोखाधड़ी जोखिम",
        "Safe / Verified": "सुरक्षित / सत्यापित",
        "Income": "आय",
        "Expense": "व्यय",
        "Savings": "बचत",
        "Investment": "निवेश",
        "Eligible": "पात्र",
        "Not Eligible": "अपात्र",
        "You Qualify": "आप पात्र हैं",
        "Needs Review": "समीक्षा आवश्यक",
        "Documents Needed": "आवश्यक दस्तावेज़",
        "Documents Checklist": "आवश्यक दस्तावेज़ सूची",
        "How to Apply": "आवेदन कैसे करें",
        "Application Process": "आवेदन प्रक्रिया",
        "Official Portal Link": "आधिकारिक पोर्टल लिंक",
        "Apply on Official Portal": "आधिकारिक पोर्टल पर आवेदन करें",
        "Open Detailed Scheme Page": "विस्तृत योजना पृष्ठ खोलें",
        "Description & Objectives": "विवरण और उद्देश्य",
        "Eligibility Requirements": "पात्रता आवश्यकताएं",
        "Scheme Benefits & Assistance": "योजना के लाभ एवं सहायता",
        "Target Gender": "लक्षित लिंग",
        "Age Limit": "आयु सीमा",
        "Area Type": "क्षेत्र प्रकार",
        "Income Cap": "आय सीमा",
        
        # Schemes & Phrases
        "Immediate Relief Assistance under Welfare and Relief for Fishermen During Lean Seasons and Natural Calamities Scheme": "मंदी के मौसम और प्राकृतिक आपदाओं के दौरान मछुआरों के लिए कल्याण और राहत योजना के तहत तत्काल राहत सहायता",
        "Welfare and Relief for Fishermen During Lean Seasons and Natural Calamities Scheme": "मंदी के मौसम और प्राकृतिक आपदाओं के दौरान मछुआरों के लिए कल्याण और राहत योजना",
        "Immediate Relief Assistance": "तत्काल राहत सहायता",
        "Welfare and Relief for Fishermen": "मछुआरों के लिए कल्याण और राहत",
        "Lean Seasons and Natural Calamities": "मंदी के मौसम और प्राकृतिक आपदाएं",
        "Consortia & Tender Marketing Scheme": "कंसोर्टिया और निविदा विपणन योजना",
        "Micro and Small Enterprises": "सूक्ष्म एवं लघु उद्यम",
        "Micro, Small and Medium Enterprises": "सूक्ष्म, लघु और मध्यम उद्यम (MSME)",
        "Direct Benefit Transfer": "प्रत्यक्ष लाभ अंतरण (DBT)",
        "Common Service Centre": "सामान्य सेवा केंद्र (CSC)",
        "Financial Assistance": "वित्तीय सहायता",
        "financial assistance": "वित्तीय सहायता",
        "Financial Support": "वित्तीय सहयोग",
        "financial support": "वित्तीय सहयोग",
        "Government of India": "भारत सरकार",
        "Central Government": "केंद्र सरकार",
        "State Government": "राज्य सरकार",
        "Ministry of": "मंत्रालय",
        "Department of": "विभाग",
        "Aadhaar Card": "आधार कार्ड",
        "Identity & Address Proof": "पहचान व पते का प्रमाण",
        "Income Certificate": "आय प्रमाण पत्र",
        "Bank Passbook": "बैंक पासबुक",
        "Bank Account": "बैंक खाता",
        "Caste Certificate": "जाति प्रमाण पत्र",
        "Ration Card": "राशन कार्ड",
        "Domicile Certificate": "निवास प्रमाण पत्र",
        "Disability Certificate": "दिव्यांगता प्रमाण पत्र",
        "Legal Heir": "कानूनी उत्तराधिकारी",
        "Missing Fisherman": "लापता मछुआरा",
        "Family (Legal Heir)": "परिवार (कानूनी उत्तराधिकारी)",
        "family (legal heir)": "परिवार (कानूनी उत्तराधिकारी)",
        "Two Installments": "दो किश्तें",
        "two installments": "दो किश्तें",
        "Installment": "किश्त",
        "installments": "किश्तें",
        "Date of Receipt of the Application": "आवेदन प्राप्ति की तिथि",
        "date of receipt of the application": "आवेदन प्राप्ति की तिथि",
        "Balance 50%": "शेष 50%",
        "Market Access": "बाजार पहुंच",
        "Consortium Formation": "कंसोर्टियम गठन",
        "Order Distribution": "ऑर्डर वितरण",
        "Credit Facilitation": "ऋण सुविधा",
        "Bulk Orders": "थोक ऑर्डर",
        "Security Deposits": "सुरक्षा जमा",
        "Disbursal": "संवितरण / वितरण",
        "Subsidized government welfare benefit": "रियायती सरकारी कल्याणकारी लाभ",
        "Subsidized": "रियायती / सब्सिडी युक्त",
        "Subsidy": "सब्सिडी (अनुदान)",
        "Interest Subsidy": "ब्याज अनुदान",
        "Interest Rate": "ब्याज दर",
        "Annual Income": "वार्षिक आय",
        "Monthly Income": "मासिक आय",
        "No Age Restriction": "कोई आयु सीमा नहीं",
        "No Limit": "कोई सीमा नहीं",
        "Both (Urban/Rural)": "दोनों (शहरी/ग्रामीण)",
        "Urban": "शहरी",
        "Rural": "ग्रामीण",
        "All": "सभी",
        "General": "सामान्य",
        "Male": "पुरुष",
        "Female": "महिला",
        "Women": "महिलाएं",
        "Farmers": "किसान",
        "Farmer": "किसान",
        "Students": "छात्र",
        "Student": "छात्र",
        "Youth": "युवा",
        "Children": "बच्चे",
        "Senior Citizens": "वरिष्ठ नागरिक",
        "Senior Citizen": "वरिष्ठ नागरिक",
        "Disabled": "दिव्यांग",
        "Beneficiary": "लाभार्थी",
        "Beneficiaries": "लाभार्थी",
        "Compensation": "मुआवजा",
        "Breadwinner": "कमाऊ सदस्य",
        "Loss": "हानि / नुकसान",
        "Support": "सहयोग / सहायता",
        "Assistance": "सहायता",
        "Benefit": "लाभ",
        "Benefits": "लाभ",
        "Scheme": "योजना",
        "Schemes": "योजनाएं",
        "Objectives": "उद्देश्य",
        "Objective": "उद्देश्य",
        "Guidelines": "दिशा-निर्देश",
        "Portal": "पोर्टल",
        "Official Website": "आधिकारिक वेबसाइट",
        "Register": "पंजीकरण करें",
        "Registration": "पंजीकरण",
        "Application": "आवेदन",
        "Apply": "आवेदन करें",
        "Applied": "आवेदन किया",
        "Approved": "स्वीकृत",
        "Sanctioned": "मंजूर",
        "Released": "जारी किया गया",
        "Documents": "दस्तावेज़",
        "Document": "दस्तावेज़",
        "Required": "आवश्यक",
        "Checklist": "जांच सूची",
        "Free": "निःशुल्क",
        "Loan": "ऋण (लोन)",
        "Credit": "ऋण / साख",
        "Insurance": "बीमा",
        "Health": "स्वास्थ्य",
        "Housing": "आवास",
        "Education": "शिक्षा",
        "Agriculture": "कृषि",
        "Business": "व्यवसाय",
        "Services": "सेवाएं",
        "Under": "के तहत",
        "under": "के तहत",
        "Per Year": "प्रति वर्ष",
        "Per Month": "प्रति माह",
        "Lakh": "लाख",
        "Crore": "करोड़",
        "Months": "महीने",
        "Month": "महीना",
        "Years": "वर्ष",
        "Year": "वर्ष",
        "Days": "दिन",
        "Day": "दिन",
        "Within": "भीतर",
        "Balance": "शेष",
        "Initially": "प्रारंभ में",
        "Facilitates": "सुगम बनाता है",
        "Enables": "सक्षम बनाता है",
        "Ensures": "सुनिश्चित करता है",
        "Helps": "मदद करता है",
        "Introduced": "शुरू किया गया",
        "Introduced to": "के उद्देश्य से शुरू किया गया",
        "Provided": "प्रदान किया गया",
        "Provides": "प्रदान करता है",
        "Extended": "प्रदान किया जाएगा",
        "Ongoing Scheme": "सक्रिय योजना — कोई अंतिम तिथि नहीं",
        "PM Mudra Yojana": "पीएम मुद्रा योजना",
        "Sukanya Samriddhi Yojana": "सुकन्या समृद्धि योजना",
        "Ayushman Bharat": "आयुष्मान भारत (पीएम-जय)",
        "Pradhan Mantri Awas Yojana": "प्रधानमंत्री आवास योजना",
    },
    "mar_Deva": {
        "Hello": "नमस्कार",
        "Welcome to ArthSaathi": "अर्थसाथी मध्ये आपले स्वागत आहे",
        "Your financial security is our priority": "आपली आर्थिक सुरक्षा आमची प्राथमिकता आहे",
        "Financial Twin": "आर्थिक ट्विन",
        "Smart Planner": "स्मार्ट नियोजक",
        "Scam Shield": "स्कॅम शील्ड",
        "Government Schemes": "सरकारी योजना",
        "High Scam Risk": "उच्च घोटाळा धोका",
        "Safe / Verified": "सुरक्षित / सत्यापित",
        "Income": "उत्पन्न",
        "Expense": "खर्च",
        "Savings": "बचत",
        "Investment": "गुंतवणूक",
        "Eligible": "पात्र",
        "Not Eligible": "अपात्र",
        "You Qualify": "तुम्ही पात्र आहात",
        "Needs Review": "पुनरावलोकन आवश्यक",
        "Documents Needed": "आवश्यक कागदपत्रे",
        "Documents Checklist": "आवश्यक कागदपत्रांची यादी",
        "How to Apply": "अर्ज कसा करावा",
        "Application Process": "अर्ज प्रक्रिया",
        "Official Portal Link": "अधिकृत पोर्टल लिंक",
        "Apply on Official Portal": "अधिकृत पोर्टलवर अर्ज करा",
        "Open Detailed Scheme Page": "सविस्तर योजना पृष्ठ उघडा",
        "Description & Objectives": "वर्णन आणि उद्दिष्टे",
        "Eligibility Requirements": "पात्रता अटी",
        "Scheme Benefits & Assistance": "योजनेचे फायदे आणि साहाय्य",
        "Target Gender": "लक्षित लिंग",
        "Age Limit": "वयोमर्यादा",
        "Area Type": "परिसर प्रकार",
        "Income Cap": "उत्पन्न मर्यादा",
        
        # Schemes & Phrases (Longest first)
        "Immediate Relief Assistance under Welfare and Relief for Fishermen During Lean Seasons and Natural Calamities Scheme": "मंदीचा काळ आणि नैसर्गिक आपत्ती दरम्यान मच्छिमारांसाठी कल्याण व मदत योजनेअंतर्गत त्वरित मदत साहाय्य",
        "Welfare and Relief for Fishermen During Lean Seasons and Natural Calamities Scheme": "मंदीचा काळ आणि नैसर्गिक आपत्ती दरम्यान मच्छिमारांसाठी कल्याण व मदत योजना",
        "Immediate Relief Assistance": "त्वरित मदत साहाय्य",
        "Welfare and Relief for Fishermen": "मच्छिमारांसाठी कल्याण व मदत",
        "Lean Seasons and Natural Calamities": "मंदीचा काळ आणि नैसर्गिक आपत्ती",
        "Consortia & Tender Marketing Scheme": "कन्सोर्टिया आणि टेंडर विपणन योजना",
        "Micro and Small Enterprises": "सूक्ष्म आणि लघु उद्योग",
        "Micro, Small and Medium Enterprises": "सूक्ष्म, लघु आणि मध्यम उद्योग (MSME)",
        "Direct Benefit Transfer": "थेट लाभ हस्तांतरण (DBT)",
        "Common Service Centre": "नागरी सुविधा केंद्र (CSC)",
        "Financial Assistance": "आर्थिक साहाय्य",
        "financial assistance": "आर्थिक साहाय्य",
        "Financial Support": "आर्थिक मदत",
        "financial support": "आर्थिक मदत",
        "Government of India": "भारत सरकार",
        "Central Government": "केंद्र सरकार",
        "State Government": "राज्य सरकार",
        "Ministry of": "मंत्रालय",
        "Department of": "विभाग",
        "Aadhaar Card": "आधार कार्ड",
        "Identity & Address Proof": "ओळख व पत्त्याचा पुरावा",
        "Income Certificate": "उत्पन्न दाखला",
        "Bank Passbook": "बँक पासबुक",
        "Bank Account": "बँक खाते",
        "Caste Certificate": "जातीचा दाखला",
        "Ration Card": "रेशन कार्ड",
        "Domicile Certificate": "रहिवासी दाखला",
        "Disability Certificate": "दिव्यांगत्व प्रमाणपत्र",
        "Legal Heir": "कायदेशीर वारसदार",
        "Missing Fisherman": "बेपत्ता मच्छिमार",
        "Family (Legal Heir)": "कुटुंब (कायदेशीर वारसदार)",
        "family (legal heir)": "कुटुंब (कायदेशीर वारसदार)",
        "Two Installments": "दोन हप्ते",
        "two installments": "दोन हप्ते",
        "Installment": "हप्ता",
        "installments": "हप्ते",
        "Date of Receipt of the Application": "अर्ज मिळाल्याची तारीख",
        "date of receipt of the application": "अर्ज मिळाल्याची तारीख",
        "Balance 50%": "उर्वरित ५०%",
        "Market Access": "बाजारपेठ उपलब्धता",
        "Consortium Formation": "कन्सोर्टियम स्थापना",
        "Order Distribution": "ऑर्डर वाटप",
        "Credit Facilitation": "कर्ज व पतपुरवठा सुलभता",
        "Bulk Orders": "मोठ्या प्रमाणात ऑर्डर्स",
        "Security Deposits": "सुरक्षा अनामत रक्कम",
        "Disbursal": "वितरण / वाटप",
        "Subsidized government welfare benefit": "सरकारी अनुदानित कल्याणकारी लाभ",
        "Subsidized": "अनुदानित",
        "Subsidy": "अनुदान",
        "Interest Subsidy": "व्याज अनुदान",
        "Interest Rate": "व्याजदर",
        "Annual Income": "वार्षिक उत्पन्न",
        "Monthly Income": "मासिक उत्पन्न",
        "No Age Restriction": "कोणतीही वयोमर्यादा नाही",
        "No Limit": "मर्यादा नाही",
        "Both (Urban/Rural)": "दोन्ही (शहरी/ग्रामीण)",
        "Urban": "शहरी",
        "Rural": "ग्रामीण",
        "All": "सर्व",
        "General": "सामान्य",
        "Male": "पुरुष",
        "Female": "महिला",
        "Women": "महिला",
        "Farmers": "शेतकरी",
        "Farmer": "शेतकरी",
        "Students": "विद्यार्थी",
        "Student": "विद्यार्थी",
        "Youth": "युवक",
        "Children": "मुले",
        "Senior Citizens": "ज्येष्ठ नागरिक",
        "Senior Citizen": "ज्येष्ठ नागरिक",
        "Disabled": "दिव्यांग",
        "Beneficiary": "लाभार्थी",
        "Beneficiaries": "लाभार्थी",
        "Compensation": "भरपाई",
        "Breadwinner": "कमावता व्यक्ती",
        "Loss": "नुकसान",
        "Support": "मदत / आधार",
        "Assistance": "साहाय्य",
        "Benefit": "लाभ",
        "Benefits": "लाभ / फायदे",
        "Scheme": "योजना",
        "Schemes": "योजना",
        "Objectives": "उद्दिष्टे",
        "Objective": "उद्दिष्ट",
        "Guidelines": "मार्गदर्शक सूचना",
        "Portal": "पोर्टल",
        "Official Website": "अधिकृत संकेतस्थळ",
        "Register": "नोंदणी करा",
        "Registration": "नोंदणी",
        "Application": "अर्ज",
        "Apply": "अर्ज करा",
        "Applied": "अर्ज केला",
        "Approved": "मंजूर",
        "Sanctioned": "मंजूर",
        "Released": "वितरित",
        "Documents": "कागदपत्रे",
        "Document": "कागदपत्र",
        "Required": "आवश्यक",
        "Checklist": "सूची",
        "Free": "मोफत",
        "Loan": "कर्ज",
        "Credit": "पत / कर्ज",
        "Insurance": "विमा",
        "Health": "आरोग्य",
        "Housing": "गृहनिर्माण",
        "Education": "शिक्षण",
        "Agriculture": "कृषी",
        "Business": "व्यवसाय",
        "Services": "सेवा",
        "Under": "अंतर्गत",
        "under": "अंतर्गत",
        "Per Year": "प्रति वर्ष",
        "Per Month": "दरमहा",
        "Lakh": "लाख",
        "Crore": "कोटी",
        "Months": "महिने",
        "Month": "महिना",
        "Years": "वर्षे",
        "Year": "वर्ष",
        "Days": "दिवस",
        "Day": "दिवस",
        "Within": "आत",
        "Balance": "शिल्लक / उर्वरित",
        "Initially": "सुरुवातीला",
        "Facilitates": "सुलभ करते",
        "Enables": "सक्षम करते",
        "Ensures": "सुनिश्चित करते",
        "Helps": "मदत करते",
        "Introduced": "सुरू केली",
        "Introduced to": "च्या उद्देशाने सुरू केली",
        "Provided": "प्रदान केले",
        "Provides": "प्रदान करते",
        "Extended": "दिले जाईल / वाढवले",
        "Approach": "संपर्क साधावा",
        "Should approach": "संपर्क साधावा",
        "This department": "हा विभाग",
        "Department": "विभाग",
        "Ongoing Scheme": "सक्रिय योजना — कोणतीही अंतिम मुदत नाही",
        "PM Mudra Yojana": "पीएम मुद्रा योजना",
        "Sukanya Samriddhi Yojana": "सुकन्या समृद्धी योजना",
        "Ayushman Bharat": "आयुष्मान भारत (पीएम-जय)",
        "Pradhan Mantri Awas Yojana": "प्रधानमंत्री आवास योजना",
    },
    "tam_Taml": {
        "Hello": "வணக்கம்",
        "Welcome to ArthSaathi": "அர்த்தசாதிக்கு உங்களை வரவேற்கிறோம்",
        "Your financial security is our priority": "உங்கள் நிதி பாதுகாப்பு எங்கள் முன்னுரிமை",
        "Financial Twin": "நிதி இரட்டை (Financial Twin)",
        "Smart Planner": "ஸ்மார்ட் பிளானர்",
        "Scam Shield": "மோசடி தடுப்பு",
        "Government Schemes": "அரசு திட்டங்கள்",
        "Eligible": "தகுதியுடையது",
        "Benefit": "நன்மை",
        "How to Apply": "எவ்வாறு விண்ணப்பிப்பது",
    },
    "tel_Telu": {
        "Hello": "నమస్కారం",
        "Welcome to ArthSaathi": "అర్థసాథికి స్వాగతం",
        "Your financial security is our priority": "మీ ఆర్థిక భద్రత మా ప్రాధాన్యత",
        "Financial Twin": "ఆర్థిక ట్విన్",
        "Smart Planner": "స్మార్ట్ ప్లానర్",
        "Scam Shield": "స్కామ్ షీల్డ్",
        "Government Schemes": "ప్రభుత్వ పథకాలు",
        "Eligible": "అర్హులు",
        "Benefit": "ప్రయోజనం",
        "How to Apply": "ఎలా దరఖాస్తు చేయాలి",
    },
    "ben_Beng": {
        "Hello": "নমস্কার",
        "Welcome to ArthSaathi": "অর্থসাথীতে আপনাকে স্বাগতম",
        "Your financial security is our priority": "আপনার আর্থিক নিরাপত্তা আমাদের অগ্রাধিকার",
        "Financial Twin": "আর্থিক টুইন",
        "Smart Planner": "স্মার্ট প্ল্যানার",
        "Scam Shield": "স্ক্যাম শিল্ড",
        "Government Schemes": "সরকারি প্রকল্প",
        "Eligible": "যোগ্য",
        "Benefit": "সুবিধা",
        "How to Apply": "কীভাবে আবেদন করবেন",
    },
    "guj_Gujr": {
        "Hello": "નમસ્તે",
        "Welcome to ArthSaathi": "અર્થસાથીમાં આપનું સ્વાગત છે",
        "Your financial security is our priority": "તમારી નાણાકીય સુરક્ષા અમારી પ્રાથમિકતા છે",
        "Financial Twin": "નાણાકીય ટ્વિન",
        "Government Schemes": "સરકારી યોજનાઓ",
        "Eligible": "પાત્ર",
        "Benefit": "લાભ",
        "How to Apply": "કેવી રીતે અરજી કરવી",
    },
    "kan_Knda": {
        "Hello": "ನಮಸ್ಕಾರ",
        "Welcome to ArthSaathi": "ಅರ್ಥಸಾಥಿಗೆ ಸುಸ್ವಾಗತ",
        "Your financial security is our priority": "ನಿಮ್ಮ ಹಣಕಾಸಿನ ಸುರಕ್ಷತೆ ನಮ್ಮ ಆದ್ಯತೆಯಾಗಿದೆ",
        "Financial Twin": "ಹಣಕಾಸು ಟ್ವಿನ್",
        "Government Schemes": "ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು",
        "Eligible": "ಅರ್ಹರು",
        "Benefit": "ಪ್ರಯೋಜನ",
        "How to Apply": "ಹೇಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಬೇಕು",
    }
}


class TranslationEngine:
    def __init__(self):
        self._models = {}
        self._tokenizers = {}
        self._ip = None
        self._lock = threading.Lock()
        
        if TORCH_AVAILABLE and torch is not None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[INFO] TranslationEngine initialized on {self.device} (PyTorch {torch.__version__}).")
        else:
            self.device = "mock-fallback"
            print("[INFO] PyTorch / IndicTransToolkit not installed in current environment. Running in lightweight fallback translation mode.")

    def _get_processor(self):
        if not TORCH_AVAILABLE or IndicProcessor is None:
            return None
        if self._ip is None:
            with self._lock:
                if self._ip is None:
                    try:
                        self._ip = IndicProcessor(inference=True)
                    except Exception as e:
                        print(f"Warning: Could not initialize IndicProcessor: {e}")
                        return None
        return self._ip

    def _load_model_and_tokenizer(self, model_name: str) -> tuple:
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch and transformers are required to load IndicTrans2 models.")

        if model_name not in self._models:
            with self._lock:
                if model_name not in self._models:
                    print(f"Loading model and tokenizer for {model_name} on {self.device}...")
                    
                    candidate_names = [model_name]
                    mirror = MIRROR_MODELS.get(model_name)
                    if mirror and mirror not in candidate_names:
                        candidate_names.append(mirror)
                    
                    last_err = None
                    for name in candidate_names:
                        try:
                            print(f"Attempting to load weights from candidate: '{name}'...")
                            tokenizer = AutoTokenizer.from_pretrained(
                                name,
                                trust_remote_code=True,
                                token=os.getenv("HF_TOKEN")
                            )
                            model = AutoModelForSeq2SeqLM.from_pretrained(
                                name,
                                trust_remote_code=True,
                                token=os.getenv("HF_TOKEN")
                            ).to(self.device)
                            
                            self._tokenizers[model_name] = tokenizer
                            self._models[model_name] = model
                            print(f"Successfully loaded {model_name} (via '{name}').")
                            last_err = None
                            break
                        except Exception as e:
                            print(f"Failed to load candidate '{name}': {e}")
                            last_err = e

                    if last_err is not None:
                        raise last_err

        return self._models[model_name], self._tokenizers[model_name]


    def _fallback_translate(self, text: str, tgt_lang: str) -> str:
        """Lightweight dictionary & glossary fallback when weights/torch are not present."""
        if not text or not str(text).strip():
            return text or ""

        lang_dict = SAMPLE_TRANSLATIONS.get(tgt_lang, SAMPLE_TRANSLATIONS.get("hin_Deva", {}))
        trimmed = text.strip()
        
        # Exact match
        if trimmed in lang_dict:
            return lang_dict[trimmed]
        
        import re
        result = text
        # Sort keys by length descending so long phrases match before individual words
        sorted_keys = sorted(lang_dict.keys(), key=len, reverse=True)
        for en_key in sorted_keys:
            trans_val = lang_dict[en_key]
            # Use word boundary if en_key is a single alphanumeric word
            if " " not in en_key and en_key.isalnum():
                pattern = re.compile(r'\b' + re.escape(en_key) + r'\b', re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(en_key), re.IGNORECASE)
            result = pattern.sub(trans_val, result)
        
        return result

    def translate_batch(self, sentences: list[str], src_lang: str, tgt_lang: str) -> list[str]:
        if not sentences:
            return []
        
        # Validate languages first
        _ = route_translation_model(src_lang, tgt_lang)

        # Direct identity if same source and target language
        if src_lang == tgt_lang:
            return sentences

        # 1. Lookup in translation cache
        cached_map = translation_cache.get_batch(src_lang, tgt_lang, sentences)
        
        results: list[Optional[str]] = [None] * len(sentences)
        unique_misses: dict[str, list[int]] = {}

        for i, s in enumerate(sentences):
            if not s or not str(s).strip():
                results[i] = s
                continue
            thash = translation_cache.hash_text(s)
            if thash in cached_map:
                results[i] = cached_map[thash]
            else:
                if s not in unique_misses:
                    unique_misses[s] = []
                unique_misses[s].append(i)

        # If all texts were cached, return immediately without invoking the model
        if not unique_misses:
            return [r if r is not None else "" for r in results]

        # 2. Fast dictionary pre-check to resolve known glossary & UI terms in 0ms
        missing_texts = list(unique_misses.keys())
        unresolved_texts: list[str] = []
        resolved_map: dict[str, str] = {}

        for s in missing_texts:
            fb = self._fallback_translate(s, tgt_lang)
            if fb and fb.strip().lower() != s.strip().lower():
                resolved_map[s] = fb
            else:
                unresolved_texts.append(s)

        # 3. Only run heavy neural inference for truly unknown sentences
        if unresolved_texts:
            if not TORCH_AVAILABLE or self.device == "mock-fallback":
                for s in unresolved_texts:
                    resolved_map[s] = self._fallback_translate(s, tgt_lang)
            else:
                try:
                    model_name = route_translation_model(src_lang, tgt_lang)
                    model, tokenizer = self._load_model_and_tokenizer(model_name)
                    ip = self._get_processor()
                    if ip is None or model is None or tokenizer is None:
                        for s in unresolved_texts:
                            resolved_map[s] = self._fallback_translate(s, tgt_lang)
                    else:
                        # Preprocess batch using IndicProcessor
                        batch = ip.preprocess_batch(unresolved_texts, src_lang=src_lang, tgt_lang=tgt_lang)
                        batch = tokenizer(batch, padding="longest", truncation=True, max_length=128, return_tensors="pt").to(self.device)
                        
                        with torch.inference_mode():
                            outputs = model.generate(**batch, num_beams=1, max_length=128, use_cache=True)
                            
                        with tokenizer.as_target_tokenizer():
                            decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True, clean_up_tokenization_spaces=True)
                        neural_results = ip.postprocess_batch(decoded, lang=tgt_lang)
                        for s, trans in zip(unresolved_texts, neural_results):
                            resolved_map[s] = trans

                except Exception as e:
                    print(f"Inference failed ({e}), falling back to offline dictionary mode.")
                    for s in unresolved_texts:
                        resolved_map[s] = self._fallback_translate(s, tgt_lang)

        new_translations = [resolved_map.get(s, s) for s in missing_texts]

        # 4. Store new translations in persistent cache
        cache_items = [(orig, trans) for orig, trans in zip(missing_texts, new_translations) if trans and trans.strip().lower() != orig.strip().lower()]
        if cache_items:
            translation_cache.set_batch(src_lang, tgt_lang, cache_items)

        # 4. Assemble final results matching original sentence order
        for text, trans in zip(missing_texts, new_translations):
            for idx in unique_misses[text]:
                results[idx] = trans

        return [r if r is not None else "" for r in results]

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        res = self.translate_batch([text], src_lang, tgt_lang)
        return res[0] if res else ""

    def is_loaded(self, model_name: str) -> bool:
        return model_name in self._models

# Global singleton engine instance
engine = TranslationEngine()

