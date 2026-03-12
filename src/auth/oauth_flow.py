"""OAuth 2.0 flow implementation for Google Drive authentication"""

import secrets
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

from src.config import GoogleDriveConfig

logger = logging.getLogger(__name__)


class OAuthFlow:
    """Handles OAuth 2.0 authorization flow for Google Drive"""
    
    def __init__(self, config: GoogleDriveConfig):
        """
        Initialize OAuth flow with configuration
        
        Args:
            config: Google Drive configuration containing client credentials
        """
        self.config = config
        self._state_store: Dict[str, str] = {}  # In-memory state storage for CSRF protection
        
    def get_authorization_url(self) -> tuple[str, str]:
        """
        Generate authorization URL for user to grant permissions
        
        Returns:
            Tuple of (authorization_url, state) where state is used for CSRF protection
            
        Raises:
            ValueError: If client credentials are not configured
        """
        if not self.config.client_id or not self.config.client_secret:
            raise ValueError("Google OAuth client ID and secret must be configured")
        
        # Generate random state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Create OAuth flow
        flow = self._create_flow()
        
        # Generate authorization URL with state parameter
        authorization_url, _ = flow.authorization_url(
            access_type='offline',  # Request refresh token
            include_granted_scopes='true',  # Incremental authorization
            state=state,
            prompt='consent'  # Force consent screen to ensure refresh token
        )
        
        # Store state for validation during callback
        self._state_store[state] = state
        
        logger.info("Generated authorization URL with state parameter")
        return authorization_url, state
    
    def handle_callback(
        self, 
        authorization_code: str, 
        state: str,
        expected_state: Optional[str] = None
    ) -> Credentials:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            authorization_code: Authorization code from OAuth callback
            state: State parameter from OAuth callback
            expected_state: Expected state value for CSRF validation (optional)
            
        Returns:
            Google OAuth2 credentials with access and refresh tokens
            
        Raises:
            ValueError: If state validation fails or authorization code is invalid
        """
        # Validate state parameter for CSRF protection
        if expected_state and state != expected_state:
            logger.error("State parameter mismatch - possible CSRF attack")
            raise ValueError("Invalid state parameter - CSRF validation failed")
        
        # Validate state exists in store
        if state not in self._state_store:
            logger.error("State parameter not found in store")
            raise ValueError("Invalid state parameter - not found in session")
        
        # Remove state from store after validation (one-time use)
        del self._state_store[state]
        
        try:
            # Create OAuth flow
            flow = self._create_flow()
            
            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)
            
            credentials = flow.credentials
            
            logger.info("Successfully exchanged authorization code for tokens")
            logger.debug(f"Token expiry: {credentials.expiry}")
            
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to exchange authorization code: {e}")
            raise ValueError(f"Failed to obtain access token: {str(e)}")
    
    def _create_flow(self) -> Flow:
        """
        Create OAuth flow instance with client configuration
        
        Returns:
            Configured OAuth flow instance
        """
        # Create client config dictionary
        client_config = {
            "web": {
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.config.redirect_uri]
            }
        }
        
        # Create flow from client config
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=self.config.scopes,
            redirect_uri=self.config.redirect_uri
        )
        
        return flow
    
    def clear_state(self, state: str) -> bool:
        """
        Clear state from store (cleanup)
        
        Args:
            state: State parameter to remove
            
        Returns:
            True if state was found and removed, False otherwise
        """
        if state in self._state_store:
            del self._state_store[state]
            return True
        return False
