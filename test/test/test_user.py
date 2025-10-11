import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
from fastapi.testclient import TestClient
from app.users import schemas
from app.users.models import User
from app.utils.logger import get_logger
import pandas as pd
from test.test_db import client, db_session, mock_redis

logger = get_logger(__name__)

@pytest.fixture
def login_data():
    return schemas.LoginRequest(email_id="alkema@bat.com", password="bat@123")


# Test for successful login
def test_login_success(client: TestClient, db_session, login_data):
    client.cookies.clear() 
    response = client.post("/login", json=login_data.dict())
    logger.info(f"{response.json()}")
    assert response.status_code == 200
    assert response.json() == {"message": "Login successful"}
    assert "bat_session_id" in response.cookies  # Ensure the 'bat_session_id' cookie is set


# Test for login failure with wrong email
def test_login_wrong_email(client: TestClient, db_session, login_data):
    client.cookies.clear() 
    login_data.email_id = "wrongemail@example.com"  # Set the wrong email here
    response = client.post("/login", json=login_data.dict())
    logger.info(f"{response.json()}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


# Test for login failure with wrong password
def test_login_wrong_password(client: TestClient, db_session, login_data):
    client.cookies.clear() 
    login_data.password = "wrongpassword"  # Set the wrong password here
    response = client.post("/login", json=login_data.dict())
    logger.info(f"{response.json()}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}


# Test for successful logout when a valid session exists
def test_logout_success(client: TestClient, login_data):
    client.cookies.clear() 
    login_response = client.post("/login", json=login_data.dict())  # Logging in first to create a session
    bat_session_id = login_response.cookies.get("bat_session_id")
    response = client.get("/logout", cookies ={"bat_session_id": bat_session_id})
    logger.info(f"{response.json()}")
    assert response.status_code == 200
    assert response.json() == {"message": "Logout successful"}
    assert "bat_session_id" not in response.cookies  # Ensure the cookie is removed

# Test for logout invalid session
def test_logout_invalid_session(client: TestClient):
    # Attempting to log out with invalid session
    client.cookies.clear() 
    response = client.get("/logout", cookies ={"bat_session_id": "invalid_session"})
    logger.info(f"{response.json()}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or expired session"}

# Test for logout no session
def test_logout_no_session(client: TestClient):
    # Attempting to log out without being logged in (no session cookie)
    client.cookies.clear() 
    response = client.get("/logout")
    logger.info(f"{response.json()}")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


#Test user route successful fetch
def test_successful_fetch_user_data(client: TestClient, db_session, login_data):
    client.cookies.clear() 
    login_response = client.post("/login", json=login_data.dict())
    bat_session_id = login_response.cookies.get("bat_session_id")
    response = client.get("/user", cookies ={"bat_session_id": bat_session_id})
    logger.info(f"{response.json()}")
    assert response.status_code == 200
    #assert response.json() == 

#Test user route invalid session
def test_fetch_user_data_invalid_session(client: TestClient):
    client.cookies.clear() 
    response = client.get("/user", cookies ={"bat_session_id": "invalid_session"})
    logger.info(f"{response.json()}")
    assert response.status_code == 401
    assert response.json() == {'detail': 'Invalid or expired session'}

#Test user no session
def test_fetch_user_data_no_session(client: TestClient):
    client.cookies.clear() 
    response = client.get("/user")
    logger.info(f"{response.json()}")
    assert response.status_code == 401
    assert response.json() == {'detail': 'Not authenticated'}
