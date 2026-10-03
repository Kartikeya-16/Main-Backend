from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class UrlPhishingDetail(BaseModel):
    url: str
    phishing_probability: float
    risk_level: str
    is_spoofed_brand: bool = False
    spoofed_target: Optional[str] = None
    reasons: List[str] = []


class ExtractedEntities(BaseModel):
    urls: List[str] = []
    upis: List[str] = []
    phones: List[str] = []
    amounts: List[str] = []
    suspicious_apks: List[str] = []


class ScamAnalyzeRequest(BaseModel):
    text: str = Field(..., description="Message text, SMS, WhatsApp forward, or URL string")
    sender: Optional[str] = Field(None, description="Optional SMS header or sender ID (e.g. 'VK-SBIINB', '+919876543210')")


class UrlAnalyzeRequest(BaseModel):
    url: str = Field(..., description="URL string to evaluate for phishing / domain spoofing")


class ScamAnalyzeResponse(BaseModel):
    risk_level: str = Field(..., description="'scam', 'suspicious', or 'safe'")
    score: float = Field(..., description="Calibrated risk probability (0.0 to 1.0)")
    scam_type: str = Field(..., description="Taxonomy classification (e.g. 'kyc_update', 'digital_arrest', 'upi_fraud', 'legit')")
    reasons: List[str] = Field(default_factory=list, description="Plain-language forensic red flags")
    urls: List[UrlPhishingDetail] = Field(default_factory=list, description="Forensic inspection details per URL")
    extracted_entities: ExtractedEntities
    advice: str = Field(..., description="Actionable safety guideline and official helpline links")
    language_detected: str = Field(..., description="Language classification (English, Hinglish, Hindi)")


class HealthResponse(BaseModel):
    status: str
    service: str = "ml-service-3-scam"
    models_loaded: Dict[str, bool]
    version: str = "1.0.0"
