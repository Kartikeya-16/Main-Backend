import io
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel, Field

from app.services.scam_analyzer import (
    analyze_scam_payload,
    get_active_threat_intel,
    extract_urls,
    extract_upi_ids,
)

router = APIRouter(prefix="/scam", tags=["Scam Shield (Pillar 3)"])


class ScamAnalyzeRequest(BaseModel):
    content: str = Field(..., description="Message text, URL string, or parsed OCR content to analyze")
    type: str = Field(default="text", description="Input type: 'text', 'url', 'image', or 'pdf'")


class ThreatIndicators(BaseModel):
    extracted_urls: List[str] = []
    extracted_upis: List[str] = []
    extracted_phones: List[str] = []
    spoofed_entities: List[str] = []


class EmergencyAction(BaseModel):
    helpline: str = "1930"
    cybercrime_portal: str = "https://cybercrime.gov.in"
    chakshu_portal: str = "https://sancharsaathi.gov.in/sfc/"
    report_guidelines: List[str] = []


class ScamAnalyzeResponse(BaseModel):
    scam_probability: float = Field(..., description="Probability of scam from 0.0 to 1.0")
    risk_level: str = Field(..., description="'HIGH', 'MEDIUM', or 'SAFE'")
    category: str = Field(..., description="Categorized scam taxonomy name")
    warning_signs: List[str] = Field(default_factory=list, description="List of forensic threat indicators")
    threat_indicators: ThreatIndicators
    recommendation: str = Field(..., description="Actionable security recommendation for the user")
    emergency_action: EmergencyAction
    language_detected: str = Field(..., description="Detected script / language code")


@router.post("/analyze", response_model=ScamAnalyzeResponse)
def analyze_scam(payload: ScamAnalyzeRequest):
    """
    Evaluates message text, SMS, WhatsApp forwards, or URL strings against
    the Indian financial scam detection engine.
    """
    if not payload.content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content cannot be empty for scam analysis.",
        )

    result = analyze_scam_payload(
        content=payload.content,
        input_type=payload.type,
    )
    return result


@router.post("/analyze-file", response_model=ScamAnalyzeResponse)
async def analyze_scam_file(
    file: UploadFile = File(...),
):
    """
    Analyzes an uploaded screenshot, receipt, or PDF notice by extracting text
    and running multi-vector phishing/fraud heuristics.
    """
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    extracted_text = ""
    lower_filename = file.filename.lower()

    # If text/csv/log file
    if lower_filename.endswith((".txt", ".csv", ".json", ".log", ".html")):
        try:
            extracted_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            extracted_text = file_bytes.decode("latin-1", errors="ignore")

    # If PDF file
    elif lower_filename.endswith(".pdf") or file_bytes.startswith(b"%PDF-"):
        try:
            import pypdf
            pdf_reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages[:5]:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        except Exception:
            # Fallback raw string decode
            extracted_text = file_bytes.decode("latin-1", errors="ignore")

    # If image file (PNG, JPG, WEBP)
    else:
        # 1. Try EasyOCR for printed & handwritten text
        try:
            import easyocr
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            ocr_lines = reader.readtext(file_bytes, detail=0)
            if ocr_lines:
                extracted_text = " ".join(ocr_lines)
        except Exception:
            extracted_text = ""

        # 2. Try OpenCV QR Code detector if no text was found or in addition to text
        if not extracted_text:
            try:
                import cv2
                import numpy as np
                nparr = np.frombuffer(file_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is not None:
                    detector = cv2.QRCodeDetector()
                    data, _, _ = detector.detectAndDecode(img)
                    if data:
                        extracted_text = f"Scanned QR code data: {data}"
            except Exception:
                pass

        # 3. Fallback raw ascii string scan
        if not extracted_text.strip():
            try:
                import re
                matches = re.findall(b"[A-Za-z0-9@_.:/?&=% -]{6,}", file_bytes)
                extracted_text = " ".join([m.decode("ascii", errors="ignore") for m in matches[:50]])
            except Exception:
                extracted_text = "Uploaded payment screenshot / QR code"

    if not extracted_text.strip():
        extracted_text = f"Uploaded file {file.filename}"

    result = analyze_scam_payload(
        content=extracted_text,
        input_type="image" if lower_filename.endswith((".png", ".jpg", ".jpeg", ".webp")) else "pdf",
    )
    return result


@router.get("/threat-intel")
def get_threat_intelligence():
    """
    Returns live threat intelligence bulletin on trending financial scams in India.
    """
    return {
        "status": "ok",
        "threats": get_active_threat_intel(),
        "national_helpline": "1930",
        "official_portals": {
            "cybercrime": "https://cybercrime.gov.in",
            "chakshu": "https://sancharsaathi.gov.in/sfc/",
            "rbi_sachet": "https://sachet.rbi.org.in/"
        }
    }
