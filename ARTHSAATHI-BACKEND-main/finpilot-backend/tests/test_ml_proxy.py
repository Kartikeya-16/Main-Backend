from unittest.mock import patch
import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture
def auth_headers():
    import uuid
    unique_email = f"proxy_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "password123"
    
    reg_res = client.post(
        "/auth/register",
        json={"email": unique_email, "password": password, "full_name": "Proxy Tester"}
    )
    assert reg_res.status_code == 201
    
    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": password}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@patch("app.api.routes.ml.call_service")
def test_proxy_public_endpoints(mock_call):
    mock_call.return_value = {"status": "ok"}
    assert client.post("/ml/health-score", json={}).status_code == 200
    assert client.post("/translate", json={}).status_code == 200
    assert client.post("/translate/batch", json={}).status_code == 200
    assert client.post("/match", json={}).status_code == 200


@patch("app.api.routes.ml.call_service")
def test_proxy_health_score_success(mock_call, auth_headers):
    mock_call.return_value = {
        "health_score": 85.0,
        "category": "EXCELLENT",
        "feature_importance": {"savings_rate": 0.4},
        "insights": ["Great job"],
        "model_version": "1.0.0"
    }
    payload = {
        "monthly_income": 80000,
        "total_monthly_emis": 10000,
        "total_monthly_expenses": 30000,
        "liquid_savings": 100000,
        "total_assets": 500000,
        "total_liabilities": 200000,
        "goals": []
    }
    res = client.post("/ml/health-score", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["health_score"] == 85.0
    mock_call.assert_called_once()


@patch("app.api.routes.ml.call_service")
def test_proxy_translate_success(mock_call, auth_headers):
    mock_call.return_value = {
        "translated_text": "नमस्ते",
        "src_lang": "eng_Latn",
        "tgt_lang": "hin_Deva"
    }
    payload = {"text": "Hello", "src_lang": "eng_Latn", "tgt_lang": "hin_Deva"}
    res = client.post("/translate", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["translated_text"] == "नमस्ते"
    mock_call.assert_called_once()


@patch("app.api.routes.ml.call_service")
def test_proxy_translate_batch_success(mock_call, auth_headers):
    mock_call.return_value = {
        "translated_texts": ["नमस्ते", "शुभ प्रभात"],
        "src_lang": "eng_Latn",
        "tgt_lang": "hin_Deva"
    }
    payload = {"texts": ["Hello", "Good morning"], "src_lang": "eng_Latn", "tgt_lang": "hin_Deva"}
    res = client.post("/translate/batch", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["translated_texts"] == ["नमस्ते", "शुभ प्रभात"]
    mock_call.assert_called_once()


@patch("app.api.routes.ml.call_service")
def test_proxy_match_success(mock_call, auth_headers):
    mock_call.return_value = {
        "total_matches": 1,
        "results": [{"slug": "pm-mudra", "name": "PM Mudra", "match_score": 90.0}]
    }
    payload = {"gender": "female", "age": 29, "state": "Maharashtra", "annual_income": 900000}
    res = client.post("/match?limit=10", json=payload, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["total_matches"] == 1
    mock_call.assert_called_once()


@patch("app.api.routes.ml.call_service")
def test_proxy_unreachable_503(mock_call, auth_headers):
    mock_call.side_effect = HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Target microservice at http://localhost:8001 is unreachable: connection refused"
    )
    res = client.post("/ml/health-score", json={"monthly_income": 50000}, headers=auth_headers)
    assert res.status_code == 503
    assert "unreachable" in res.json()["detail"]


@patch("app.api.routes.ml.call_service")
def test_proxy_error_passthrough_400(mock_call, auth_headers):
    mock_call.side_effect = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported source language: invalid_lang"
    )
    res = client.post("/translate", json={"text": "Hello", "src_lang": "invalid_lang"}, headers=auth_headers)
    assert res.status_code == 400
    assert "Unsupported source language" in res.json()["detail"]


@patch("app.api.routes.ml.call_service")
def test_proxy_get_scheme_by_slug(mock_call):
    mock_call.return_value = {"slug": "astpss", "name": "AICTE Scheme", "match_score": 90.0}
    res = client.get("/schemes/astpss")
    assert res.status_code == 200
    assert res.json()["slug"] == "astpss"
    mock_call.assert_called_once()


@patch("app.api.routes.ml.call_service")
def test_proxy_translate_health(mock_call):
    mock_call.return_value = {
        "status": "ok",
        "device": "mock-fallback",
        "loaded_models": {"en-indic": False, "indic-en": False, "indic-indic": False},
        "model_version": "200M/320M dist",
    }
    res = client.get("/translate/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    mock_call.assert_called_once()


@patch("app.api.routes.ml.call_service")
def test_proxy_translate_realistic_scheme_payload(mock_call):
    """
    Ensures realistic multi-sentence government scheme text (including markdown and tags)
    is accepted by /translate with 45.0s timeout and returns Marathi translation.
    """
    scheme_text = (
        '₹ 1,00,000, in two installments of ₹ 50,000 each, as immediate relief assistance '
        'for the family (legal heir) of the missing fisherman.\n<br>\n\n> **Disbursal**\n\n'
        '- Initially, 50% will be extended within 3 months from the date of receipt of the application.\n'
        '- The family (legal heir) should approach this department for release of balance 50%.\n'
        'Aadhaar Card and Bank Passbook required.'
    )
    mock_call.return_value = {
        "translated_text": (
            '₹ 1,00,000, in दोन हप्ते of ₹ 50,000 each, as त्वरित मदत साहाय्य '
            'for the कुटुंब (कायदेशीर वारसदार) of the बेपत्ता मच्छिमार.\n<br>\n\n> **वितरण / वाटप**\n\n'
            '- सुरुवातीला, 50% will be extended आत 3 महिने from the अर्ज मिळाल्याची तारीख.\n'
            '- The कुटुंब (कायदेशीर वारसदार) संपर्क साधावा हा विभाग for release of उर्वरित ५०%.\n'
            'आधार कार्ड and बँक पासबुक आवश्यक.'
        ),
        "src_lang": "eng_Latn",
        "tgt_lang": "mar_Deva",
    }

    payload = {
        "text": scheme_text,
        "src_lang": "eng_Latn",
        "tgt_lang": "mar_Deva",
    }

    res = client.post("/translate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "translated_text" in data
    assert "त्वरित मदत साहाय्य" in data["translated_text"]
    assert "कुटुंब (कायदेशीर वारसदार)" in data["translated_text"]
    # Check that call_service was invoked with timeout=45.0
    _, kwargs = mock_call.call_args
    assert kwargs.get("timeout") == 45.0


@patch("app.api.routes.ml.call_service")
def test_proxy_translate_batch_realistic_schemes(mock_call):
    """
    Ensures batch of realistic scheme descriptions and titles does not fail or timeout.
    """
    names = [
        'Immediate Relief Assistance under Welfare and Relief for Fishermen During Lean Seasons and Natural Calamities Scheme',
        'Consortia & Tender Marketing Scheme',
        'PM Mudra Yojana'
    ]
    benefits = [
        '₹ 1,00,000 in two installments as immediate relief assistance for family (legal heir).',
        'Financial assistance in security deposits and credit facilitation for micro and small enterprises.',
        'Low interest loans up to ₹ 10 Lakh with subsidized interest rates for small business units.'
    ]
    all_texts = names + benefits

    mock_call.return_value = {
        "translated_texts": [f"Trans_{i}" for i in range(len(all_texts))],
        "src_lang": "eng_Latn",
        "tgt_lang": "mar_Deva",
    }

    res = client.post("/translate/batch", json={"texts": all_texts, "src_lang": "eng_Latn", "tgt_lang": "mar_Deva"})
    assert res.status_code == 200
    assert len(res.json()["translated_texts"]) == 6
    _, kwargs = mock_call.call_args
    assert kwargs.get("timeout") == 45.0


@patch("app.api.routes.ml.call_service")
def test_proxy_translate_cache_response(mock_call):
    """
    Verifies that the proxy correctly relays cached batch translation responses
    from ml-service-2-translation and verifies response structure.
    """
    cached_response = {
        "translated_texts": [
            "मुख्यमंत्री रोजगार निर्मिती कार्यक्रम (CMEGP)",
            "पात्र व्यक्तींना आर्थिक सहाय्य व कर्ज अनुदान."
        ],
        "src_lang": "eng_Latn",
        "tgt_lang": "mar_Deva"
    }
    mock_call.return_value = cached_response

    payload = {
        "texts": [
            "Chief Minister Employment Generation Programme (CMEGP)",
            "Financial assistance and loan subsidy for eligible individuals."
        ],
        "src_lang": "eng_Latn",
        "tgt_lang": "mar_Deva"
    }

    # First request
    res1 = client.post("/translate/batch", json=payload)
    assert res1.status_code == 200
    assert res1.json()["translated_texts"][0] == "मुख्यमंत्री रोजगार निर्मिती कार्यक्रम (CMEGP)"

    # Second request
    res2 = client.post("/translate/batch", json=payload)
    assert res2.status_code == 200
    assert res2.json()["translated_texts"] == cached_response["translated_texts"]
    assert mock_call.call_count == 2
