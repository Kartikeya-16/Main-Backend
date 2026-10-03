from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    ScamAnalyzeRequest,
    ScamAnalyzeResponse,
    UrlAnalyzeRequest,
    UrlPhishingDetail,
    HealthResponse,
)
from app.models.text_classifier import text_predictor
from app.models.url_classifier import url_predictor
from app.fusion import fuse_risk


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure models are loaded
    print("[ml-service-3-scam] Initializing ML models...")
    text_predictor.load_model()
    url_predictor.load_model()
    yield


app = FastAPI(
    title="Arthsaathi ML Service 3 — Scam & Phishing Detection",
    description="4-stage hybrid microservice evaluating messages and URLs against Indian financial scam threats.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health Check"])
def health_check():
    """Returns service health status and model load states."""
    return HealthResponse(
        status="ok",
        service="ml-service-3-scam",
        models_loaded={
            "text_scam_model": text_predictor.is_loaded(),
            "url_phish_model": url_predictor.is_loaded(),
        },
        version="1.0.0",
    )


@app.post("/scam/analyze", response_model=ScamAnalyzeResponse, tags=["Scam Analysis"])
def analyze_message(payload: ScamAnalyzeRequest):
    """
    Executes the 4-stage hybrid pipeline on an SMS, WhatsApp forward, or text message.
    """
    if not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message text cannot be empty.",
        )

    result = fuse_risk(text=payload.text, sender=payload.sender)
    return result


@app.post("/scam/url", response_model=UrlPhishingDetail, tags=["URL Phishing Analysis"])
def evaluate_single_url(payload: UrlAnalyzeRequest):
    """
    Evaluates a single URL string for domain spoofing, suspicious TLDs, and lexical phishing patterns.
    """
    if not payload.url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL cannot be empty.",
        )

    result = url_predictor.evaluate_url(payload.url)
    return result
