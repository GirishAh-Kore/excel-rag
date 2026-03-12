"""Unit tests for authentication module"""

import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from google.oauth2.credentials import Credentials

from src.config import GoogleDriveConfig
from src.auth import (
    OAuthFlow,
    TokenStorage,
    TokenRefreshManager,
    AuthenticationService,
    AuthenticationStatus,
    generate_encryption_key
)


@pytest.fixture
def google_drive_config():
    """Create test Google Drive configuration"""
    return GoogleDriveConfig(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/callback",
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        token_storage_path=tempfile.mkdtemp(),
        token_encryption_key=generate_encryption_key()
    )


@pytest.fixture
def mock_credentials():
    """Create mock credentials"""
    creds = Mock(spec=Credentials)
    creds.token = "test_access_token"
    creds.refresh_token = "test_refresh_token"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.client_id = "test_client_id"
    creds.client_secret = "test_client_secret"
    creds.scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds.expiry = datetime.utcnow() + timedelta(hours=1)
    return creds


class TestOAuthFlow:
    """Tests for OAuthFlow"""
    
    def test_get_authorization_url(self, google_drive_config):
        """Test authorization URL generation"""
        oauth = OAuthFlow(google_drive_config)
        auth_url, state = oauth.get_authorization_url()
        
        assert auth_url is not None
        assert "accounts.google.com" in auth_url
        assert state is not None
        assert len(state) > 20  # Should be a secure random string
    
    def test_authorization_url_contains_scopes(self, google_drive_config):
        """Test that authorization URL includes scopes"""
        oauth = OAuthFlow(google_drive_config)
        auth_url, state = oauth.get_authorization_url()
        
        assert "scope=" in auth_url
        assert "drive.readonly" in auth_url
    
    def test_state_parameter_stored(self, google_drive_config):
        """Test that state parameter is stored for validation"""
        oauth = OAuthFlow(google_drive_config)
        auth_url, state = oauth.get_authorization_url()
        
        assert state in oauth._state_store
    
    def test_invalid_config_raises_error(self):
        """Test that invalid config raises error"""
        config = GoogleDriveConfig(
            client_id="",
            client_secret="",
            redirect_uri="http://localhost:8000/callback",
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
            token_storage_path="/tmp/tokens",
            token_encryption_key="test_key"
        )
        
        oauth = OAuthFlow(config)
        with pytest.raises(ValueError):
            oauth.get_authorization_url()


class TestTokenStorage:
    """Tests for TokenStorage"""
    
    def test_save_and_load_credentials(self, google_drive_config, mock_credentials):
        """Test saving and loading credentials"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        
        # Save credentials
        assert storage.save_credentials(mock_credentials)
        
        # Load credentials
        loaded_creds = storage.load_credentials()
        assert loaded_creds is not None
        assert loaded_creds.token == mock_credentials.token
        assert loaded_creds.refresh_token == mock_credentials.refresh_token
    
    def test_credentials_exist(self, google_drive_config, mock_credentials):
        """Test checking if credentials exist"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        
        # Initially no credentials
        assert not storage.credentials_exist()
        
        # Save credentials
        storage.save_credentials(mock_credentials)
        
        # Now credentials exist
        assert storage.credentials_exist()
    
    def test_delete_credentials(self, google_drive_config, mock_credentials):
        """Test deleting credentials"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        
        # Save credentials
        storage.save_credentials(mock_credentials)
        assert storage.credentials_exist()
        
        # Delete credentials
        assert storage.delete_credentials()
        assert not storage.credentials_exist()
    
    def test_load_nonexistent_credentials(self, google_drive_config):
        """Test loading credentials when none exist"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        
        loaded_creds = storage.load_credentials()
        assert loaded_creds is None


class TestTokenRefreshManager:
    """Tests for TokenRefreshManager"""
    
    def test_is_token_expired_valid_token(self, google_drive_config, mock_credentials):
        """Test checking if valid token is expired"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        refresh_manager = TokenRefreshManager(storage)
        
        # Token expires in 1 hour - should not be expired
        mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
        assert not refresh_manager.is_token_expired(mock_credentials)
    
    def test_is_token_expired_expiring_soon(self, google_drive_config, mock_credentials):
        """Test checking if token expiring soon is considered expired"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        refresh_manager = TokenRefreshManager(storage)
        
        # Token expires in 2 minutes - should be considered expired (buffer is 5 min)
        mock_credentials.expiry = datetime.utcnow() + timedelta(minutes=2)
        assert refresh_manager.is_token_expired(mock_credentials)
    
    def test_is_token_expired_no_expiry(self, google_drive_config, mock_credentials):
        """Test checking token with no expiry time"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        refresh_manager = TokenRefreshManager(storage)
        
        # No expiry time - should be considered expired
        mock_credentials.expiry = None
        assert refresh_manager.is_token_expired(mock_credentials)
    
    def test_get_time_until_expiry(self, google_drive_config, mock_credentials):
        """Test getting time until token expiry"""
        storage = TokenStorage(
            storage_path=google_drive_config.token_storage_path,
            encryption_key=google_drive_config.token_encryption_key
        )
        refresh_manager = TokenRefreshManager(storage)
        
        # Token expires in 1 hour
        mock_credentials.expiry = datetime.utcnow() + timedelta(hours=1)
        time_left = refresh_manager.get_time_until_expiry(mock_credentials)
        
        assert time_left is not None
        assert 3500 < time_left < 3700  # Approximately 1 hour (3600 seconds)


class TestAuthenticationService:
    """Tests for AuthenticationService"""
    
    def test_initialization(self, google_drive_config):
        """Test authentication service initialization"""
        auth_service = AuthenticationService(google_drive_config)
        
        assert auth_service.config == google_drive_config
        assert auth_service.oauth_flow is not None
        assert auth_service.token_storage is not None
        assert auth_service.token_refresh_manager is not None
    
    def test_is_authenticated_no_credentials(self, google_drive_config):
        """Test authentication check with no credentials"""
        auth_service = AuthenticationService(google_drive_config)
        
        assert not auth_service.is_authenticated()
    
    def test_get_authentication_status_not_authenticated(self, google_drive_config):
        """Test getting status when not authenticated"""
        auth_service = AuthenticationService(google_drive_config)
        
        status = auth_service.get_authentication_status()
        assert status == AuthenticationStatus.NOT_AUTHENTICATED
    
    def test_initiate_oauth_flow(self, google_drive_config):
        """Test initiating OAuth flow"""
        auth_service = AuthenticationService(google_drive_config)
        
        auth_url, state = auth_service.initiate_oauth_flow()
        
        assert auth_url is not None
        assert state is not None
        assert "accounts.google.com" in auth_url


class TestEncryptionKeyGeneration:
    """Tests for encryption key generation"""
    
    def test_generate_encryption_key(self):
        """Test generating encryption key"""
        key = generate_encryption_key()
        
        assert key is not None
        assert len(key) > 30  # Should be a base64-encoded key
        assert isinstance(key, str)
    
    def test_generated_keys_are_unique(self):
        """Test that generated keys are unique"""
        key1 = generate_encryption_key()
        key2 = generate_encryption_key()
        
        assert key1 != key2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
