"""
FastAPI application for the Government Scheme Generator microservice (scheme-service-1).
"""
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict
import pandas as pd
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from app.data_loader import load_schemes
from app.matcher import match_schemes
from app.schemas import HealthResponse, MatchResponse, UserProfile

logger = logging.getLogger("scheme-service.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load dataset into memory at service startup."""
    try:
        df = load_schemes()
        logger.info(f"Loaded {len(df)} schemes into memory on startup.")
    except Exception as e:
        logger.warning(f"Could not pre-load schemes dataset on startup: {e}")
    yield


app = FastAPI(
    title="ArthSaathi Scheme Generator Service — Scheme Service 1",
    description="Microservice to match user profiles against Indian government schemes dataset.",
    version="1.0.0",
    lifespan=lifespan,
)

# Open CORS middleware configuration for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health Check"])
def health_check():
    """Returns service health status and total count of schemes loaded in memory."""
    try:
        df = load_schemes()
        schemes_count = len(df)
    except Exception:
        schemes_count = 0

    return HealthResponse(status="ok", schemes_loaded=schemes_count)


@app.post("/schemes/match", response_model=MatchResponse, tags=["Scheme Matching"])
def match_user_schemes(
    profile: UserProfile,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of matched schemes to return"),
):
    """
    Evaluates a UserProfile payload against loaded schemes and returns ranked results.
    """
    try:
        df = load_schemes()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scheme dataset unavailable: {str(e)}",
        )

    results = match_schemes(profile=profile, df=df, limit=limit)
    return MatchResponse(total_matches=len(results), results=results)


@app.get("/schemes/{slug}", tags=["Scheme Details"])
def get_scheme_by_slug(slug: str) -> Dict[str, Any]:
    """
    Retrieves full details for a single scheme by its unique slug.
    """
    try:
        df = load_schemes()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Scheme dataset unavailable: {str(e)}",
        )

    matched_rows = df[df["slug"] == slug]
    if matched_rows.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheme with slug '{slug}' not found",
        )

    record = matched_rows.iloc[0].to_dict()
    # Clean out any non-serializable pandas NaNs to None
    for k, v in record.items():
        if hasattr(v, "item"):  # numpy scalars
            v = v.item()
        if isinstance(v, float) and pd.isna(v):
            record[k] = None
        else:
            record[k] = v

    return record
