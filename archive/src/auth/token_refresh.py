"""Automatic token refresh functionality"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

from src.auth.token_storage import TokenStorage

logger = logging.getLogger(__name__)


class TokenRefreshManager:
    """Manages automatic token refresh with expiration checking"""
    
    # Buffer time before expiry to trigger refresh (5 minutes)
    REFRESH_BUFFER_SECONDS = 300
    
    def __init__(self, token_storage: TokenStorage):
        """
        Initialize token refresh manager
        
        Args:
            token_storage: TokenStorage instance for loading/saving credentials
        """
        self.token_storage = token_storage
    
    def is_token_expired(self, credentials: Credentials) -> bool:
        """
        Check if token is expired or will expire soon
        
        Args:
            credentials: Google OAuth2 credentials to check
            
        Returns:
            True if token is expired or will expire within buffer time
        """
        if not credentials.expiry:
            logger.warning("Credentials have no expiry time - assuming expired")
            return True
        
        # Calculate time until expiry
        now = datetime.utcnow()
        time_until_expiry = (credentials.expiry - now).total_seconds()
        
        # Check if expired or will expire within buffer
        is_expired = time_until_expiry <= self.REFRESH_BUFFER_SECONDS
        
        if is_expired:
            logger.info(f"Token expired or expiring soon (expires in {time_until_expiry:.0f} seconds)")
        else:
            logger.debug(f"Token valid for {time_until_expiry:.0f} more seconds")
        
        return is_expired
    
    def refresh_token(self, credentials: Credentials) -> Optional[Credentials]:
        """
        Refresh access token using refresh token
        
        Args:
            credentials: Credentials with refresh token
            
        Returns:
            Updated credentials with new access token, or None if refresh failed
        """
        if not credentials.refresh_token:
            logger.error("No refresh token available - cannot refresh")
            return None
        
        try:
            logger.info("Attempting to refresh access token...")
            
            # Create request object for token refresh
            request = Request()
            
            # Refresh the credentials
            credentials.refresh(request)
            
            logger.info("Token refreshed successfully")
            logger.debug(f"New token expiry: {credentials.expiry}")
            
            # Save updated credentials
            if self.token_storage.update_token(credentials):
                logger.info("Updated credentials saved to storage")
            else:
                logger.warning("Failed to save updated credentials")
            
            return credentials
            
        except RefreshError as e:
            logger.error(f"Token refresh failed: {e}")
            logger.info("User will need to re-authenticate")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            return None
    
    def ensure_valid_token(self, credentials: Optional[Credentials]) -> Optional[Credentials]:
        """
        Ensure credentials have a valid token, refreshing if necessary
        
        Args:
            credentials: Credentials to validate and potentially refresh
            
        Returns:
            Valid credentials, or None if refresh failed or no credentials provided
        """
        if not credentials:
            logger.debug("No credentials provided")
            return None
        
        # Check if token needs refresh
        if self.is_token_expired(credentials):
            logger.info("Token expired or expiring soon - refreshing...")
            credentials = self.refresh_token(credentials)
            
            if not credentials:
                logger.error("Token refresh failed - authentication required")
                return None
        
        return credentials
    
    def get_valid_credentials(self) -> Optional[Credentials]:
        """
        Load credentials from storage and ensure they are valid
        
        Returns:
            Valid credentials, or None if not available or refresh failed
        """
        # Load credentials from storage
        credentials = self.token_storage.load_credentials()
        
        if not credentials:
            logger.info("No stored credentials found")
            return None
        
        # Ensure token is valid (refresh if needed)
        return self.ensure_valid_token(credentials)
    
    def get_time_until_expiry(self, credentials: Credentials) -> Optional[float]:
        """
        Get time in seconds until token expires
        
        Args:
            credentials: Credentials to check
            
        Returns:
            Seconds until expiry, or None if no expiry time available
        """
        if not credentials.expiry:
            return None
        
        now = datetime.utcnow()
        time_until_expiry = (credentials.expiry - now).total_seconds()
        
        return max(0, time_until_expiry)
    
    def should_refresh(self, credentials: Credentials) -> bool:
        """
        Determine if token should be refreshed proactively
        
        Args:
            credentials: Credentials to check
            
        Returns:
            True if token should be refreshed, False otherwise
        """
        return self.is_token_expired(credentials)
