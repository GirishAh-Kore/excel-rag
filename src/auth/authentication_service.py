"""Main authentication service that orchestrates OAuth flow, token storage, and refresh"""

import logging
from typing import Optional
from enum import Enum

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from src.config import GoogleDriveConfig
from src.auth.oauth_flow import OAuthFlow
from src.auth.token_storage import TokenStorage
from src.auth.token_refresh import TokenRefreshManager

logger = logging.getLogger(__name__)


class AuthenticationStatus(Enum):
    """Authentication status states"""
    NOT_AUTHENTICATED = "not_authenticated"
    AUTHENTICATED = "authenticated"
    TOKEN_EXPIRED = "token_expired"
    REFRESH_FAILED = "refresh_failed"


class AuthenticationService:
    """
    Main authentication service for Google Drive
    
    Orchestrates OAuth flow, secure token storage, and automatic token refresh
    """
    
    def __init__(self, config: GoogleDriveConfig):
        """
        Initialize authentication service
        
        Args:
            config: Google Drive configuration
        """
        self.config = config
        self.oauth_flow = OAuthFlow(config)
        self.token_storage = TokenStorage(
            storage_path=config.token_storage_path,
            encryption_key=config.token_encryption_key
        )
        self.token_refresh_manager = TokenRefreshManager(self.token_storage)
        
        logger.info("Authentication service initialized")
    
    def initiate_oauth_flow(self) -> tuple[str, str]:
        """
        Initiate OAuth 2.0 authorization flow
        
        Returns:
            Tuple of (authorization_url, state) for user to complete authorization
            
        Raises:
            ValueError: If OAuth configuration is invalid
        """
        try:
            auth_url, state = self.oauth_flow.get_authorization_url()
            logger.info("OAuth flow initiated - user should visit authorization URL")
            return auth_url, state
        except Exception as e:
            logger.error(f"Failed to initiate OAuth flow: {e}")
            raise
    
    def handle_oauth_callback(
        self, 
        authorization_code: str, 
        state: str,
        expected_state: Optional[str] = None
    ) -> bool:
        """
        Handle OAuth callback and store credentials
        
        Args:
            authorization_code: Authorization code from OAuth callback
            state: State parameter from OAuth callback
            expected_state: Expected state value for CSRF validation
            
        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            # Exchange code for credentials
            credentials = self.oauth_flow.handle_callback(
                authorization_code=authorization_code,
                state=state,
                expected_state=expected_state
            )
            
            # Save credentials securely
            if self.token_storage.save_credentials(credentials):
                logger.info("Authentication successful - credentials saved")
                return True
            else:
                logger.error("Failed to save credentials")
                return False
                
        except Exception as e:
            logger.error(f"OAuth callback handling failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """
        Check if user is authenticated with valid credentials
        
        Returns:
            True if authenticated with valid credentials, False otherwise
        """
        credentials = self.token_refresh_manager.get_valid_credentials()
        return credentials is not None
    
    def get_authentication_status(self) -> AuthenticationStatus:
        """
        Get detailed authentication status
        
        Returns:
            Current authentication status
        """
        # Check if credentials exist
        if not self.token_storage.credentials_exist():
            return AuthenticationStatus.NOT_AUTHENTICATED
        
        # Load credentials
        credentials = self.token_storage.load_credentials()
        if not credentials:
            return AuthenticationStatus.NOT_AUTHENTICATED
        
        # Check if token is expired
        if self.token_refresh_manager.is_token_expired(credentials):
            # Try to refresh
            refreshed = self.token_refresh_manager.refresh_token(credentials)
            if refreshed:
                return AuthenticationStatus.AUTHENTICATED
            else:
                return AuthenticationStatus.REFRESH_FAILED
        
        return AuthenticationStatus.AUTHENTICATED
    
    def get_authenticated_client(self, service_name: str = "drive", version: str = "v3") -> Optional[Resource]:
        """
        Get authenticated Google API client
        
        Args:
            service_name: Google API service name (default: "drive")
            version: API version (default: "v3")
            
        Returns:
            Authenticated Google API client, or None if authentication failed
            
        Raises:
            ValueError: If not authenticated or authentication failed
        """
        try:
            # Get valid credentials (will refresh if needed)
            credentials = self.token_refresh_manager.get_valid_credentials()
            
            if not credentials:
                logger.error("No valid credentials available")
                raise ValueError("Not authenticated - please complete OAuth flow first")
            
            # Build and return authenticated client
            client = build(service_name, version, credentials=credentials)
            logger.info(f"Created authenticated {service_name} {version} client")
            
            return client
            
        except HttpError as e:
            logger.error(f"HTTP error creating authenticated client: {e}")
            raise ValueError(f"Failed to create authenticated client: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating authenticated client: {e}")
            raise ValueError(f"Authentication error: {str(e)}")
    
    def revoke_access(self) -> bool:
        """
        Revoke access and delete stored credentials
        
        Returns:
            True if revocation was successful, False otherwise
        """
        try:
            # Load credentials
            credentials = self.token_storage.load_credentials()
            
            if credentials and credentials.token:
                # Revoke token with Google
                try:
                    from google.auth.transport.requests import Request
                    import requests
                    
                    revoke_url = "https://oauth2.googleapis.com/revoke"
                    params = {'token': credentials.token}
                    
                    response = requests.post(revoke_url, params=params)
                    
                    if response.status_code == 200:
                        logger.info("Token revoked successfully with Google")
                    else:
                        logger.warning(f"Token revocation returned status {response.status_code}")
                        
                except Exception as e:
                    logger.warning(f"Failed to revoke token with Google: {e}")
                    # Continue with local deletion even if revocation fails
            
            # Delete stored credentials
            if self.token_storage.delete_credentials():
                logger.info("Stored credentials deleted")
                return True
            else:
                logger.error("Failed to delete stored credentials")
                return False
                
        except Exception as e:
            logger.error(f"Error during access revocation: {e}")
            return False
    
    def get_credentials(self) -> Optional[Credentials]:
        """
        Get current valid credentials
        
        Returns:
            Valid credentials, or None if not authenticated
        """
        return self.token_refresh_manager.get_valid_credentials()
    
    def refresh_credentials(self) -> bool:
        """
        Manually trigger credential refresh
        
        Returns:
            True if refresh was successful, False otherwise
        """
        credentials = self.token_storage.load_credentials()
        if not credentials:
            logger.error("No credentials to refresh")
            return False
        
        refreshed = self.token_refresh_manager.refresh_token(credentials)
        return refreshed is not None


# Factory function for creating authentication service
def create_authentication_service(config: GoogleDriveConfig) -> AuthenticationService:
    """
    Factory function to create authentication service
    
    Args:
        config: Google Drive configuration
        
    Returns:
        Configured authentication service instance
    """
    return AuthenticationService(config)
