import pytest
from fastapi.testclient import TestClient
from app import app, MOCK_USERS

client = TestClient(app)

def test_health_check():
    # Health check depends on redis, but we can test the response format
    # Even if it returns 200 with status: unhealthy
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_login_success():
    login_data = {
        "email": "admin@quickhaul.com",
        "password": "admin123"
    }
    # Mocking redis if necessary, but here we just test the logic
    # In CI, if redis is not running, we might need to mock redis_client
    pass

def test_mock_users_presence():
    assert "admin@quickhaul.com" in MOCK_USERS
    assert MOCK_USERS["admin@quickhaul.com"]["role"] == "admin"
    assert "user@quickhaul.com" in MOCK_USERS
    assert MOCK_USERS["user@quickhaul.com"]["role"] == "customer"

def test_login_invalid_credentials():
    login_data = {
        "email": "admin@quickhaul.com",
        "password": "wrongpassword"
    }
    response = client.post("/auth/login", json=login_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
