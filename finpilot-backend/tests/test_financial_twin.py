import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_financial_twin_and_sub_models():
    # 1. Register and login a unique user to test with
    unique_email = f"twin_test_{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    full_name = "Financial Twin User"

    # Register
    reg_response = client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": password,
            "full_name": full_name
        }
    )
    assert reg_response.status_code == 201

    # Login
    login_response = client.post(
        "/auth/login",
        json={
            "email": unique_email,
            "password": password
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    access_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    # 2. Test GET /financial-twin (should return 404 since it's not created yet)
    get_twin_response = client.get("/financial-twin", headers=headers)
    assert get_twin_response.status_code == 404

    # 3. Test POST /financial-twin (Create twin)
    twin_payload = {
        "occupation": "Software Engineer",
        "occupation_type": "SALARIED",
        "monthly_income": 120000.00,
        "state": "Maharashtra",
        "city": "Mumbai",
        "age": 28,
        "education_level": "GRADUATE",
        "marital_status": "SINGLE",
        "dependents_count": 0,
        "has_elderly_parents": True,
        "risk_appetite": "MEDIUM"
    }
    create_twin_response = client.post("/financial-twin", json=twin_payload, headers=headers)
    assert create_twin_response.status_code == 201
    twin_data = create_twin_response.json()
    assert twin_data["occupation"] == "Software Engineer"
    assert float(twin_data["monthly_income"]) == 120000.00
    assert twin_data["risk_appetite"] == "MEDIUM"
    assert "id" in twin_data

    # 4. Test POST /financial-twin again (Conflict validation, should return 409)
    create_again_response = client.post("/financial-twin", json=twin_payload, headers=headers)
    assert create_again_response.status_code == 409

    # 5. Test GET /financial-twin (Retrieve twin)
    get_twin_response = client.get("/financial-twin", headers=headers)
    assert get_twin_response.status_code == 200
    assert get_twin_response.json()["occupation"] == "Software Engineer"

    # 6. Test PUT /financial-twin (Update twin)
    update_payload = {
        "occupation": "Tech Lead",
        "monthly_income": 150000.00,
        "risk_appetite": "HIGH"
    }
    update_twin_response = client.put("/financial-twin", json=update_payload, headers=headers)
    assert update_twin_response.status_code == 200
    updated_data = update_twin_response.json()
    assert updated_data["occupation"] == "Tech Lead"
    assert float(updated_data["monthly_income"]) == 150000.00
    assert updated_data["risk_appetite"] == "HIGH"
    assert updated_data["city"] == "Mumbai"  # Unchanged field remains the same

    # 7. Test Income CRUD
    income_payload = {
        "source": "Primary Salary",
        "amount": 150000.00,
        "frequency": "MONTHLY",
        "description": "Monthly pay from day job"
    }
    add_income_response = client.post("/income", json=income_payload, headers=headers)
    assert add_income_response.status_code == 201
    assert add_income_response.json()["source"] == "Primary Salary"

    get_income_response = client.get("/income", headers=headers)
    assert get_income_response.status_code == 200
    income_list = get_income_response.json()
    assert len(income_list) == 1
    assert income_list[0]["source"] == "Primary Salary"

    # 8. Test Expenses CRUD
    expense_payload = {
        "category": "HOUSING",
        "amount": 35000.00,
        "frequency": "MONTHLY",
        "description": "Apartment rent"
    }
    add_expense_response = client.post("/expenses", json=expense_payload, headers=headers)
    assert add_expense_response.status_code == 201
    assert add_expense_response.json()["category"] == "HOUSING"

    get_expense_response = client.get("/expenses", headers=headers)
    assert get_expense_response.status_code == 200
    expense_list = get_expense_response.json()
    assert len(expense_list) == 1
    assert expense_list[0]["category"] == "HOUSING"

    # 9. Test Assets CRUD
    asset_payload = {
        "asset_type": "MUTUAL_FUNDS",
        "name": "Nifty 50 Index Fund",
        "current_value": 500000.00,
        "description": "Equity long term mutual fund"
    }
    add_asset_response = client.post("/assets", json=asset_payload, headers=headers)
    assert add_asset_response.status_code == 201
    assert add_asset_response.json()["name"] == "Nifty 50 Index Fund"

    get_asset_response = client.get("/assets", headers=headers)
    assert get_asset_response.status_code == 200
    asset_list = get_asset_response.json()
    assert len(asset_list) == 1
    assert asset_list[0]["name"] == "Nifty 50 Index Fund"

    # 10. Test Liabilities CRUD
    liability_payload = {
        "liability_type": "CAR_LOAN",
        "name": "HDFC Auto Loan",
        "principal_amount": 800000.00,
        "outstanding_amount": 650000.00,
        "emi_amount": 18500.00,
        "interest_rate": 8.75,
        "description": "Auto loan for SUV"
    }
    add_liability_response = client.post("/liabilities", json=liability_payload, headers=headers)
    assert add_liability_response.status_code == 201
    assert add_liability_response.json()["name"] == "HDFC Auto Loan"

    get_liability_response = client.get("/liabilities", headers=headers)
    assert get_liability_response.status_code == 200
    liability_list = get_liability_response.json()
    assert len(liability_list) == 1
    assert liability_list[0]["name"] == "HDFC Auto Loan"

    # 11. Test Financial Goals CRUD
    goal_payload = {
        "title": "Retirement Fund",
        "goal_type": "RETIREMENT",
        "target_amount": 50000000.00,
        "current_savings": 500000.00,
        "target_date": "2055-12-31",
        "priority": "HIGH",
        "status": "ACTIVE"
    }
    add_goal_response = client.post("/goals", json=goal_payload, headers=headers)
    assert add_goal_response.status_code == 201
    assert add_goal_response.json()["title"] == "Retirement Fund"

    get_goal_response = client.get("/goals", headers=headers)
    assert get_goal_response.status_code == 200
    goal_list = get_goal_response.json()
    assert len(goal_list) == 1
    assert goal_list[0]["title"] == "Retirement Fund"
