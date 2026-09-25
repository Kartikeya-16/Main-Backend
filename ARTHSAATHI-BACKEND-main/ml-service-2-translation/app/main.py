import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from app.languages import LANGUAGES, EN_INDIC_MODEL, INDIC_EN_MODEL, INDIC_INDIC_MODEL
from app.schemas import TranslateRequest, TranslateResponse, BatchTranslateRequest, BatchTranslateResponse
from app.model import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # App startup logic
    # Warm up IndicProcessor to cache assets
    print("Initializing translation engine processor...")
    engine._get_processor()
    yield
    # App shutdown logic
    pass

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Arthsaathi ML Service 2 — Translation Service",
    description="Offline microservice to translate text between English and 22 Indian languages.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/translate", response_model=TranslateResponse, tags=["Translation"])
def translate_text(payload: TranslateRequest):
    """
    Translates a single block of text between English and 22 scheduled Indian languages.
    """
    try:
        translated = engine.translate(
            text=payload.text,
            src_lang=payload.src_lang,
            tgt_lang=payload.tgt_lang
        )
        return TranslateResponse(
            translated_text=translated,
            src_lang=payload.src_lang,
            tgt_lang=payload.tgt_lang
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Translation failed: {str(e)}"
        )

@app.post("/translate/batch", response_model=BatchTranslateResponse, tags=["Translation"])
def translate_batch_texts(payload: BatchTranslateRequest):
    """
    Translates multiple sentences in a single batch request.
    """
    try:
        translated_list = engine.translate_batch(
            sentences=payload.texts,
            src_lang=payload.src_lang,
            tgt_lang=payload.tgt_lang
        )
        return BatchTranslateResponse(
            translated_texts=translated_list,
            src_lang=payload.src_lang,
            tgt_lang=payload.tgt_lang
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch translation failed: {str(e)}"
        )

@app.get("/languages", tags=["Languages"])
def get_supported_languages():
    """
    Returns the supported FLORES-200 language code mapping.
    """
    return LANGUAGES

from app.cache import translation_cache

@app.get("/health", tags=["Health Check"])
def health_check():
    """
    Verifies service status, PyTorch device status, loaded models, and cache stats.
    """
    is_real = engine.device in ("cuda", "cpu", "mps") and engine.device != "mock-fallback"
    return {
        "status": "ok",
        "device": engine.device,
        "is_real_model": is_real,
        "loaded_models": {
            "en-indic": engine.is_loaded(EN_INDIC_MODEL),
            "indic-en": engine.is_loaded(INDIC_EN_MODEL),
            "indic-indic": engine.is_loaded(INDIC_INDIC_MODEL),
        },
        "model_version": "200M/320M dist",
        "cache": translation_cache.stats()
    }

@app.get("/cache/stats", tags=["Cache"])
def get_cache_stats():
    """
    Returns statistics about the SQLite translation cache.
    """
    return translation_cache.stats()

