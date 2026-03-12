"""Integration tests for web application authentication flow"""

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


class TestAuthenticationFlow:
    """Test authentication flow for web application"""
    
    def test_login_with_correct_credentials(self):
        """Test login with correct username and password"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "girish",
                "password": "Girish@123"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "access_token" in data
        assert "token_type" in data
        assert "expires_in" in data
        assert "username" in data
        
        # Verify response values
        assert data["token_type"] == "bearer"
        assert data["username"] == "girish"
        assert data["expires_in"] > 0
        assert len(data["access_token"]) > 0
    
    def test_login_with_incorrect_username(self):
        """Test login with incorrect username"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "wrong_user",
                "password": "Girish@123"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid username or password" in data["detail"]
    
    def test_login_with_incorrect_password(self):
        """Test login with incorrect password"""
        response = client.post(
            "/api/auth/login",
            json={
                "username": "girish",
                "password": "wrong_password"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        assert "Invalid username or password" in data["detail"]
    
    def test_login_with_missing_credentials(self):
        """Test login with missing credentials"""
        response = client.post(
            "/api/auth/login",
            json={}
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_session_persistence_with_valid_token(self):
        """Test that valid token can be used for authenticated requests"""
        # First, login to get token
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "girish",
                "password": "Girish@123"
            }
        )
        
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Use token to check status
        status_response = client.get(
            "/api/auth/status",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        assert status_data["authenticated"] is True
        assert status_data["username"] == "girish"
        assert "expires_at" in status_data
    
    def test_logout_functionality(self):
        """Test logout functionality"""
        # First, login to get token
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "girish",
                "password": "Girish@123"
            }
        )
        
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        
        # Logout
        logout_response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert logout_response.status_code == 200
        logout_data = logout_response.json()
        
        assert logout_data["success"] is True
        assert "message" in logout_data
    
    def test_protected_route_without_authentication(self):
        """Test accessing protected route without authentication"""
        # Try to logout without token
        response = client.post("/api/auth/logout")
        
        assert response.status_code == 403  # Forbidden (no credentials)
    
    def test_protected_route_with_invalid_token(self):
        """Test accessing protected route with invalid token"""
        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        
        assert response.status_code == 401  # Unauthorized
    
    def test_status_without_authentication(self):
        """Test status endpoint without authentication"""
        response = client.get("/api/auth/status")
        
        # Status endpoint should return 403 when no credentials provided
        assert response.status_code == 403
    
    def test_status_with_invalid_token(self):
        """Test status endpoint with invalid token"""
        response = client.get(
            "/api/auth/status",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should return not authenticated for invalid token
        assert data["authenticated"] is False
        assert data["username"] is None
    
    def test_token_expiration_info(self):
        """Test that token expiration information is provided"""
        login_response = client.post(
            "/api/auth/login",
            json={
                "username": "girish",
                "password": "Girish@123"
            }
        )
        
        assert login_response.status_code == 200
        data = login_response.json()
        
        # Check expires_in is reasonable (should be 24 hours = 86400 seconds)
        assert data["expires_in"] > 86000  # Allow some margin
        assert data["expires_in"] <= 86400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
