import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.languages import LANGUAGES

client = TestClient(app)

def test_get_languages():
    response = client.get("/languages")
    assert response.status_code == 200
    data = response.json()
    assert "eng_Latn" in data
    assert "hin_Deva" in data
    assert data["eng_Latn"] == "English"

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "device" in data

def test_invalid_language():
    payload = {
        "text": "Hello",
        "src_lang": "invalid_code",
        "tgt_lang": "hin_Deva"
    }
    response = client.post("/translate", json=payload)
    assert response.status_code == 400
    assert "Unsupported source language" in response.json()["detail"]

def test_same_languages():
    payload = {
        "text": "Hello",
        "src_lang": "eng_Latn",
        "tgt_lang": "eng_Latn"
    }
    response = client.post("/translate", json=payload)
    assert response.status_code == 400
    assert "must be different" in response.json()["detail"]

@pytest.mark.integration
def test_real_translation_smoke():
    # End-to-end smoke test: actually loads the model (e.g. eng->indic)
    # and translates a simple sentence to prove weights can be fetched and loaded.
    payload = {
        "text": "How are you?",
        "src_lang": "eng_Latn",
        "tgt_lang": "hin_Deva"
    }
    response = client.post("/translate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "translated_text" in data
    assert len(data["translated_text"]) > 0
    print(f"\nSmoke Test Translation Result: {data['translated_text']}")
