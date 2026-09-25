from fastapi.testclient import TestClient
import pytest
from app.main import app

client = TestClient(app)


def test_auth_workflow():
    # Use a unique email to avoid conflicts with previous test runs
    import uuid
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    password = "securepassword123"
    full_name = "Tushaar Capstone"

    # 1. Register a new user
    reg_response = client.post(
        "/auth/register",
        json={
            "email": unique_email,
            "password": password,
            "full_name": full_name
        }
    )
    assert reg_response.status_code == 201
    reg_data = reg_response.json()
    assert reg_data["email"] == unique_email
    assert reg_data["full_name"] == full_name
    assert "id" in reg_data
    assert "hashed_password" not in reg_data

    # 2. Login with registered user
    login_response = client.post(
        "/auth/login",
        json={
            "email": unique_email,
            "password": password
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

    access_token = token_data["access_token"]
    refresh_token = token_data["refresh_token"]

    # 3. Call GET /auth/me with the access token
    headers = {"Authorization": f"Bearer {access_token}"}
    me_response = client.get("/auth/me", headers=headers)
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["email"] == unique_email
    assert me_data["full_name"] == full_name

    # 4. Refresh the access token using the refresh token
    refresh_response = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert refresh_response.status_code == 200
    new_token_data = refresh_response.json()
    assert "access_token" in new_token_data
    assert "refresh_token" in new_token_data
    
    new_access_token = new_token_data["access_token"]
    
    # Verify the new access token works
    new_headers = {"Authorization": f"Bearer {new_access_token}"}
    new_me_response = client.get("/auth/me", headers=new_headers)
    assert new_me_response.status_code == 200
    assert new_me_response.json()["email"] == unique_email


def test_login_invalid_credentials():
    # Login with non-existent credentials
    login_response = client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
    )
    assert login_response.status_code == 401
    assert login_response.json()["detail"] == "Incorrect email or password"


def test_protected_route_without_token():
    # Attempt to access /auth/me without authorization headers
    response = client.get("/auth/me")
    assert response.status_code == 401
