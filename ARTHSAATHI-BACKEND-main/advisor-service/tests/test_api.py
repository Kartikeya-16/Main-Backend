import os
import io
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def test_advisor_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "advisor-service"}


def test_api_parse_csv():
    with open(os.path.join(FIXTURES_DIR, "hdfc_sample.csv"), "rb") as f:
        res = client.post("/parse", files={"file": ("hdfc_sample.csv", f, "text/csv")})
    assert res.status_code == 200
    data = res.json()
    assert data["bank"] == "HDFC Bank"
    assert len(data["txns"]) == 4
    assert data["reconciled"] is True
    assert isinstance(data["txns"][0]["balance"], str)  # Serialized as decimal string


def test_api_parse_encrypted_pdf():
    # 1. Missing password
    with open(os.path.join(FIXTURES_DIR, "encrypted_sample.pdf"), "rb") as f:
        res_no_pw = client.post("/parse", files={"file": ("encrypted_sample.pdf", f, "application/pdf")})
    assert res_no_pw.status_code == 401

    # 2. Wrong password
    with open(os.path.join(FIXTURES_DIR, "encrypted_sample.pdf"), "rb") as f:
        res_wrong = client.post(
            "/parse",
            files={"file": ("encrypted_sample.pdf", f, "application/pdf")},
            data={"password": "WrongPassword"},
        )
    assert res_wrong.status_code == 422

    # 3. Correct password
    with open(os.path.join(FIXTURES_DIR, "encrypted_sample.pdf"), "rb") as f:
        res_correct = client.post(
            "/parse",
            files={"file": ("encrypted_sample.pdf", f, "application/pdf")},
            data={"password": "Secret123"},
        )
    assert res_correct.status_code == 200
    assert res_correct.json()["reconciled"] is True


def test_api_empty_file():
    res = client.post("/parse", files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")})
    assert res.status_code == 400


def test_api_unsupported_format():
    with open(os.path.join(FIXTURES_DIR, "unsupported.txt"), "rb") as f:
        res = client.post("/parse", files={"file": ("unsupported.txt", f, "text/plain")})
    assert res.status_code == 422
