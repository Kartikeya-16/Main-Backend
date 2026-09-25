from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.microservice_client import call_service

router = APIRouter(tags=["Microservice Proxy Layer"])


@router.post("/ml/health-score")
async def proxy_ml_health_score(
    payload: Dict[str, Any],
):
    """
    Proxy forwarding requests to ml-service-1 (port 8001).
    Target endpoint: POST /ml/health-score
    """
    return await call_service(
        service_base_url=settings.ML_SERVICE_1_URL,
        path="/ml/health-score",
        method="POST",
        json_data=payload,
    )


@router.get("/translate/health")
async def proxy_translate_health():
    """
    Proxy forwarding health check to ml-service-2-translation (port 8002).
    Target endpoint: GET /health
    """
    return await call_service(
        service_base_url=settings.ML_SERVICE_2_URL,
        path="/health",
        method="GET",
        timeout=10.0,
        
    )


@router.get("/translate/languages")
async def proxy_translate_languages():
    """
    Proxy forwarding supported languages lookup to ml-service-2-translation (port 8002).
    Target endpoint: GET /languages
    """
    return await call_service(
        service_base_url=settings.ML_SERVICE_2_URL,
        path="/languages",
        method="GET",
        timeout=10.0,
    )


@router.post("/translate")
async def proxy_translate(
    payload: Dict[str, Any],
):
    """
    Proxy forwarding requests to ml-service-2-translation (port 8002).
    Target endpoint: POST /translate
    """
    return await call_service(
        service_base_url=settings.ML_SERVICE_2_URL,
        path="/translate",
        method="POST",
        json_data=payload,
        timeout=45.0,
    )


@router.post("/translate/batch")
async def proxy_translate_batch(
    payload: Dict[str, Any],
):
    """
    Proxy forwarding batch requests to ml-service-2-translation (port 8002).
    Target endpoint: POST /translate/batch
    """
    return await call_service(
        service_base_url=settings.ML_SERVICE_2_URL,
        path="/translate/batch",
        method="POST",
        json_data=payload,
        timeout=45.0,
    )


@router.post("/match")
async def proxy_scheme_match(
    payload: Dict[str, Any],
    limit: Optional[int] = Query(20, ge=1, le=100),
):
    """
    Proxy forwarding requests to scheme-service-1 (port 8003).
    Target endpoint: POST /schemes/match
    """
    params = {"limit": limit} if limit is not None else None
    return await call_service(
        service_base_url=settings.SCHEME_SERVICE_URL,
        path="/schemes/match",
        method="POST",
        json_data=payload,
        params=params,
    )


@router.get("/schemes/{slug}")
async def proxy_get_scheme(slug: str):
    """
    Proxy forwarding single scheme lookup to scheme-service-1 (port 8003).
    Target endpoint: GET /schemes/{slug}
    """
    return await call_service(
        service_base_url=settings.SCHEME_SERVICE_URL,
        path=f"/schemes/{slug}",
        method="GET",
    )
