import uuid
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def get_authenticated_user_headers(prefix: str = "advisor_user"):
    unique_email = f"{prefix}_{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    full_name = "Advisor Test User"

    reg_res = client.post(
        "/auth/register",
        json={"email": unique_email, "password": password, "full_name": full_name},
    )
    assert reg_res.status_code == 201

    login_res = client.post(
        "/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_advisor_routes_require_jwt():
    routes = [
        ("GET", "/advisor/questionnaire"),
        ("GET", "/advisor/meta"),
        ("POST", "/advisor/plan"),
        ("GET", "/advisor/profile-draft"),
    ]
    for method, path in routes:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401, f"{path} did not return 401 without auth"


@patch("app.api.routes.advisor.advisor_questionnaire")
def test_advisor_questionnaire_proxy(mock_q):
    mock_q.return_value = {"questions": [{"id": "risk_tolerance", "text": "What is your risk?"}]}
    headers = get_authenticated_user_headers("q_test")
    res = client.get("/advisor/questionnaire", headers=headers)
    assert res.status_code == 200
    assert "questions" in res.json()
    mock_q.assert_called_once()


@patch("app.api.routes.advisor.advisor_meta")
def test_advisor_meta_proxy(mock_meta):
    mock_meta.return_value = {"categories": ["EQUITY", "DEBT"]}
    headers = get_authenticated_user_headers("meta_test")
    res = client.get("/advisor/meta", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"categories": ["EQUITY", "DEBT"]}
    mock_meta.assert_called_once()


@patch("app.api.routes.advisor.advisor_plan")
def test_advisor_plan_proxy(mock_plan):
    mock_plan.return_value = {"plan_id": "test_plan_123", "first_action": "emergency_fund"}
    headers = get_authenticated_user_headers("plan_test")
    payload = {"monthly_income_inr": 100000}
    res = client.post("/advisor/plan", json=payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["first_action"] == "emergency_fund"
    mock_plan.assert_called_once_with(payload)


@patch("app.api.routes.advisor.advisor_plan")
def test_advisor_plan_422_pass_through(mock_plan):
    mock_plan.side_effect = HTTPException(status_code=422, detail="Missing required field: age")
    headers = get_authenticated_user_headers("plan_422")
    res = client.post("/advisor/plan", json={}, headers=headers)
    assert res.status_code == 422
    assert "Missing required field: age" in res.json()["detail"]


@patch("app.api.routes.advisor.advisor_plan")
def test_advisor_plan_503_when_advisor_down(mock_plan):
    mock_plan.side_effect = HTTPException(status_code=503, detail="Advisor service unavailable")
    headers = get_authenticated_user_headers("plan_503")
    res = client.post("/advisor/plan", json={"age": 30}, headers=headers)
    assert res.status_code == 503
    assert "Advisor service unavailable" in res.json()["detail"]


def test_advisor_profile_draft_404_no_twin():
    headers = get_authenticated_user_headers("no_twin")
    res = client.get("/advisor/profile-draft", headers=headers)
    assert res.status_code == 404
    assert "Create your Financial Twin first" in res.json()["detail"]


def test_advisor_profile_draft_with_twin():
    headers = get_authenticated_user_headers("twin_draft")
    
    # 1. Create twin
    twin_payload = {
        "occupation": "Product Manager",
        "occupation_type": "SALARIED",
        "monthly_income": 200000.00,
        "state": "Karnataka",
        "city": "Bengaluru",
        "age": 32,
        "education_level": "POST_GRADUATE",
        "marital_status": "MARRIED",
        "dependents_count": 2,
        "has_elderly_parents": False,
        "risk_appetite": "HIGH"
    }
    r_twin = client.post("/financial-twin", json=twin_payload, headers=headers)
    assert r_twin.status_code == 201

    # 2. Add incomes: Monthly 100,000 + Annual 120,000 (10k/mo)
    client.post("/income", json={"source": "Salary", "amount": 100000.0, "frequency": "MONTHLY"}, headers=headers)
    client.post("/income", json={"source": "Bonus", "amount": 120000.0, "frequency": "ANNUAL"}, headers=headers)  # 10,000/mo

    # 3. Add expenses: Monthly 40,000 + Annual 60,000 (5,000/mo)
    client.post("/expenses", json={"category": "HOUSING", "amount": 40000.0, "frequency": "MONTHLY"}, headers=headers)
    client.post("/expenses", json={"category": "UTILITIES", "amount": 60000.0, "frequency": "ANNUAL"}, headers=headers)

    # 4. Add assets: 1 liquid SAVINGS, 1 liquid FIXED_DEPOSIT, 1 non-liquid REAL_ESTATE
    client.post("/assets", json={"asset_type": "SAVINGS", "name": "HDFC Savings", "current_value": 150000.0}, headers=headers)
    client.post("/assets", json={"asset_type": "FIXED_DEPOSIT", "name": "SBI FD", "current_value": 250000.0}, headers=headers)
    client.post("/assets", json={"asset_type": "REAL_ESTATE", "name": "Apartment", "current_value": 6000000.0}, headers=headers)

    # 5. Add liability
    client.post("/liabilities", json={
        "liability_type": "HOME_LOAN",
        "name": "Home Loan",
        "principal_amount": 5000000.0,
        "outstanding_amount": 4500000.0,
        "emi_amount": 45000.0,
        "interest_rate": 8.5
    }, headers=headers)

    # 6. Add goals: one valid future goal, one past goal, one undated goal
    client.post("/goals", json={
        "title": "Kids College",
        "goal_type": "EDUCATION",
        "target_amount": 2500000.0,
        "current_savings": 200000.0,
        "target_date": "2036-06-30",
        "priority": "HIGH",
        "status": "ACTIVE"
    }, headers=headers)
    client.post("/goals", json={
        "title": "Old Laptop Goal",
        "goal_type": "OTHER",
        "target_amount": 100000.0,
        "current_savings": 100000.0,
        "target_date": "2020-01-01",
        "priority": "LOW",
        "status": "ACHIEVED"
    }, headers=headers)
    client.post("/goals", json={
        "title": "Undated Dream Trip",
        "goal_type": "TRAVEL",
        "target_amount": 300000.0,
        "current_savings": 50000.0,
        "target_date": None,
        "priority": "MEDIUM",
        "status": "ACTIVE"
    }, headers=headers)

    # 7. Get profile draft
    res = client.get("/advisor/profile-draft", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert "profile" in data
    assert "missing_fields" in data
    assert "skipped_goals" in data

    profile = data["profile"]
    # Income: 100000 + (120000/12 = 10000) = 110000.0
    assert profile["monthly_income_inr"] == 110000.0
    # Expense: 40000 + (60000/12 = 5000) = 45000.0
    assert profile["monthly_expenses_inr"] == 45000.0
    # Liquid assets: 150000 + 250000 = 400000.0 (REAL_ESTATE not included)
    assert profile["emergency_fund_inr"] == 400000.0

    # Liabilities
    assert len(profile["liabilities"]) == 1
    assert profile["liabilities"][0]["type"] == "HOME_LOAN"
    assert profile["liabilities"][0]["outstanding_amount"] == 4500000.0
    assert profile["liabilities"][0]["interest_rate"] == 8.5
    assert profile["liabilities"][0]["emi_amount"] == 45000.0

    # Goals: Only Kids College included
    assert len(profile["goals"]) == 1
    valid_goal = profile["goals"][0]
    assert valid_goal["name"] == "Kids College"
    assert valid_goal["target_amount"] == 2500000.0
    assert valid_goal["current_savings"] == 200000.0
    assert valid_goal["years"] >= 9

    # Skipped goals
    assert len(data["skipped_goals"]) == 2
    skipped_names = [sg["name"] for sg in data["skipped_goals"]]
    assert "Old Laptop Goal" in skipped_names
    assert "Undated Dream Trip" in skipped_names

    # Demographics from Twin
    assert profile["age"] == 32
    assert profile["dependents"] == 2

    # Missing fields: age is present from twin, so only daughters_under_10, insurance, tax_regime, risk_answers
    assert "age" not in data["missing_fields"]
    assert "daughters_under_10" in data["missing_fields"]
    assert "tax_regime" in data["missing_fields"]
    assert "risk_answers" in data["missing_fields"]
    assert "insurance" in data["missing_fields"]

    # Source map verification
    assert "source" in data
    assert data["source"]["age"] == "twin"
    assert data["source"]["dependents"] == "twin"
    assert data["source"]["monthly_income_inr"] == "twin"
    assert data["source"]["monthly_expenses_inr"] == "twin"
    assert data["source"]["emergency_fund_inr"] == "twin"
    assert data["source"]["liabilities"] == "twin"
    assert data["source"]["goals"] == "twin"

    # Twin gaps (this user has income, expenses, liquid assets, goals, so no gaps)
    assert "twin_gaps" in data
    assert len(data["twin_gaps"]) == 0


def test_advisor_profile_draft_twin_gaps():
    headers = get_authenticated_user_headers("twin_gaps_user")

    # Create twin with monthly_income=0 and no items
    twin_payload = {
        "occupation": "Freelancer",
        "occupation_type": "SELF_EMPLOYED",
        "monthly_income": 0.0,
        "state": "Goa",
        "city": "Panaji",
        "age": 28,
        "education_level": "GRADUATE",
        "marital_status": "SINGLE",
        "dependents_count": 0,
        "has_elderly_parents": False,
        "risk_appetite": "MEDIUM"
    }
    client.post("/financial-twin", json=twin_payload, headers=headers)

    res = client.get("/advisor/profile-draft", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert len(data["twin_gaps"]) >= 3
    gap_fields = [g["field"] for g in data["twin_gaps"]]
    assert "monthly_income_inr" in gap_fields
    assert "monthly_expenses_inr" in gap_fields
    assert "emergency_fund_inr" in gap_fields
    assert "goals" in gap_fields
    for gap in data["twin_gaps"]:
        assert gap["link"] == "/twin"
