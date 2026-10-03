import pytest
from fastapi.testclient import TestClient
from app.main import app

EXCELLENT_PROFILE = {
    "monthly_income": 100000.0,
    "total_monthly_emis": 10000.0,       # 10% EMI ratio — very healthy
    "total_monthly_expenses": 40000.0,   # 40% expense ratio
    "liquid_savings": 600000.0,          # 6 months emergency fund
    "total_assets": 5000000.0,
    "total_liabilities": 500000.0,       # 10x asset/liability ratio
    "goals": [{"target_amount": 1000000.0, "current_savings": 500000.0}]  # 50% progress
}

POOR_PROFILE = {
    "monthly_income": 30000.0,
    "total_monthly_emis": 20000.0,       # 67% EMI ratio — dangerous
    "total_monthly_expenses": 28000.0,   # 93% expense ratio
    "liquid_savings": 10000.0,           # less than 1 month emergency fund
    "total_assets": 50000.0,
    "total_liabilities": 200000.0,       # 0.25x asset/liability ratio
    "goals": [{"target_amount": 500000.0, "current_savings": 5000.0}]   # 1% progress
}


@pytest.fixture(scope="module")
def client():
    # Use context manager to trigger lifespan startup/shutdown events
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model"] == "loaded"
    assert data["model_version"] == "1.0.0"


def test_excellent_profile(client):
    response = client.post("/ml/health-score", json=EXCELLENT_PROFILE)
    assert response.status_code == 200
    data = response.json()
    assert data["health_score"] >= 80.0
    assert data["category"] == "EXCELLENT"
    assert "emi_to_income_ratio" in data["feature_importance"]


def test_poor_profile(client):
    response = client.post("/ml/health-score", json=POOR_PROFILE)
    assert response.status_code == 200
    data = response.json()
    assert data["health_score"] <= 40.0
    assert data["category"] == "POOR"


def test_high_emi_insights(client):
    # Make a copy of excellent profile but with very high EMI
    high_emi_profile = dict(EXCELLENT_PROFILE)
    high_emi_profile["total_monthly_emis"] = 65000.0  # 65% ratio
    
    response = client.post("/ml/health-score", json=high_emi_profile)
    assert response.status_code == 200
    data = response.json()
    # Insights should mention EMI
    insights_str = " ".join(data["insights"]).lower()
    assert "emi" in insights_str or "debt" in insights_str


def test_no_emergency_fund_insights(client):
    # Make a copy of excellent profile but with critical liquid savings
    low_savings_profile = dict(EXCELLENT_PROFILE)
    low_savings_profile["liquid_savings"] = 0.0
    
    response = client.post("/ml/health-score", json=low_savings_profile)
    assert response.status_code == 200
    data = response.json()
    insights_str = " ".join(data["insights"]).lower()
    assert "emergency" in insights_str


def test_empty_goals_list(client):
    no_goals_profile = dict(EXCELLENT_PROFILE)
    no_goals_profile["goals"] = []
    
    response = client.post("/ml/health-score", json=no_goals_profile)
    assert response.status_code == 200
    data = response.json()
    assert "health_score" in data
    assert data["category"] in ["POOR", "FAIR", "GOOD", "EXCELLENT"]
