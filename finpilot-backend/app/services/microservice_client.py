from typing import Any, Dict, Optional
import httpx
from fastapi import HTTPException, status


async def call_service(
    service_base_url: str,
    path: str,
    method: str = "POST",
    json_data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """
    Helper to forward HTTP requests to backend microservices using httpx.
    Supports smart fallback between Docker network names and localhost/127.0.0.1
    so requests succeed in both local host-run and containerized environments.
    """
    candidates = [service_base_url]
    
    # Auto-generate dual candidate for host vs docker container networks
    if ":8001" in service_base_url:
        candidates = list(dict.fromkeys([service_base_url, "http://ml-service-1:8001", "http://127.0.0.1:8001", "http://localhost:8001"]))
    elif ":8002" in service_base_url:
        candidates = list(dict.fromkeys([service_base_url, "http://ml-service-2-translation:8002", "http://127.0.0.1:8002", "http://localhost:8002"]))
    elif ":8003" in service_base_url:
        candidates = list(dict.fromkeys([service_base_url, "http://scheme-service-1:8003", "http://127.0.0.1:8003", "http://localhost:8003"]))
    elif ":8005" in service_base_url:
        candidates = list(dict.fromkeys([service_base_url, "http://advisor-service:8005", "http://127.0.0.1:8005", "http://localhost:8005"]))

    last_exc = None
    response = None

    for base in candidates:
        url = f"{base.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                )
            if response is not None:
                break
        except httpx.RequestError as exc:
            last_exc = exc
            continue

    if response is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Target microservice at {service_base_url} is unreachable: {str(last_exc)}",
        )

    if response.is_error:
        try:
            err_json = response.json()
            detail = err_json.get("detail", response.text)
        except Exception:
            detail = response.text or f"Microservice error ({response.status_code})"

        raise HTTPException(
            status_code=response.status_code,
            detail=detail,
        )

    try:
        return response.json()
    except Exception:
        return {"raw_response": response.text}


async def forward_statement_parse(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    password: Optional[str] = None,
    ai_key: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """
    Forwards statement file and optional password/ai_key to advisor-service /parse endpoint
    as multipart/form-data via httpx.
    """
    from app.core.config import settings

    candidates = list(dict.fromkeys([
        settings.ADVISOR_SERVICE_URL,
        "http://advisor-service:8005",
        "http://127.0.0.1:8005",
        "http://localhost:8005",
    ]))

    data = {}
    if password:
        data["password"] = password
    if ai_key:
        data["ai_key"] = ai_key

    last_exc = None
    response = None

    for base in candidates:
        url = f"{base.rstrip('/')}/parse"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                files = {"file": (filename, file_bytes, content_type)}
                response = await client.post(
                    url=url,
                    files=files,
                    data=data if data else None,
                )
            if response is not None:
                break
        except httpx.RequestError as exc:
            last_exc = exc
            continue

    if response is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Advisor parsing service is unreachable: {str(last_exc)}",
        )

    if response.is_error:
        try:
            err_json = response.json()
            detail = err_json.get("detail", response.text)
        except Exception:
            detail = response.text or f"Advisor service error ({response.status_code})"

        raise HTTPException(
            status_code=response.status_code,
            detail=detail,
        )

    try:
        return response.json()
    except Exception:
        return {"raw_response": response.text}


async def _call_advisor_endpoint(
    path: str,
    method: str = "GET",
    json_data: Optional[Dict[str, Any]] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    from app.core.config import settings

    candidates = list(dict.fromkeys([
        settings.ADVISOR_SERVICE_URL,
        "http://advisor-service:8005",
        "http://127.0.0.1:8005",
        "http://localhost:8005",
    ]))

    last_exc = None
    response = None

    for base in candidates:
        url = f"{base.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_data,
                )
            if response is not None:
                break
        except httpx.RequestError as exc:
            last_exc = exc
            continue

    if response is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Advisor service unavailable",
        )

    if response.is_error:
        try:
            err_json = response.json()
            detail = err_json.get("detail", response.text)
        except Exception:
            detail = response.text or f"Advisor service error ({response.status_code})"

        raise HTTPException(
            status_code=response.status_code,
            detail=detail,
        )

    try:
        return response.json()
    except Exception:
        return {"raw_response": response.text}


async def advisor_questionnaire() -> Dict[str, Any]:
    """
    Proxies request to GET /advisor/questionnaire on advisor-service.
    """
    return await _call_advisor_endpoint(path="/advisor/questionnaire", method="GET")


async def advisor_meta() -> Dict[str, Any]:
    """
    Proxies request to GET /advisor/meta on advisor-service.
    """
    return await _call_advisor_endpoint(path="/advisor/meta", method="GET")


async def advisor_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Proxies request to POST /advisor/plan on advisor-service.
    """
    return await _call_advisor_endpoint(path="/advisor/plan", method="POST", json_data=payload)

