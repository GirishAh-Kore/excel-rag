"""Google Drive configuration endpoints for web application"""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from src.api.web_auth import get_current_user
from src.api.dependencies import get_auth_service
from src.auth.authentication_service import AuthenticationService
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class GDriveConnectResponse(BaseModel):
    """Response for Google Drive connect initiation"""
    authorization_url: str
    state: str
    message: str


class GDriveCallbackRequest(BaseModel):
    """Request for OAuth callback"""
    code: str
    state: str


class GDriveCallbackResponse(BaseModel):
    """Response for OAuth callback"""
    success: bool
    message: str
    user_email: Optional[str] = None


class GDriveDisconnectResponse(BaseModel):
    """Response for Google Drive disconnect"""
    success: bool
    message: str


class GDriveStatusResponse(BaseModel):
    """Response for Google Drive connection status"""
    connected: bool
    user_email: Optional[str] = None
    token_expiry: Optional[datetime] = None
    scopes: Optional[list[str]] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/connect", response_model=GDriveConnectResponse)
async def connect_gdrive(
    current_user: str = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Initiate Google Drive OAuth connection
    
    Returns authorization URL for user to grant permissions.
    """
    logger.info(f"Google Drive connect request from user {current_user}")
    
    try:
        # Generate OAuth authorization URL
        auth_url, state = auth_service.initiate_oauth_flow()
        
        logger.info(f"Generated OAuth URL for user {current_user}")
        
        return GDriveConnectResponse(
            authorization_url=auth_url,
            state=state,
            message="Please authorize access to Google Drive"
        )
    
    except Exception as e:
        logger.error(f"Failed to initiate OAuth flow: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/callback", response_model=GDriveCallbackResponse)
async def gdrive_callback(
    code: str = Query(..., description="Authorization code from OAuth"),
    state: str = Query(..., description="State parameter for validation"),
    current_user: str = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Handle Google Drive OAuth callback
    
    - **code**: Authorization code from Google OAuth
    - **state**: State parameter for CSRF protection
    """
    logger.info(f"Google Drive OAuth callback for user {current_user}")
    
    try:
        # Handle OAuth callback and exchange code for tokens
        success = auth_service.handle_oauth_callback(code, state)
        
        if not success:
            logger.warning(f"OAuth callback failed for user {current_user}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth callback failed. Invalid code or state."
            )
        
        # Get user email from credentials
        user_email = None
        try:
            if auth_service.is_authenticated():
                # Try to get user info
                client = auth_service.get_authenticated_client()
                # Note: Getting user email requires additional API call
                # For now, we'll just indicate success
                user_email = "authenticated"
        except:
            pass
        
        logger.info(f"Google Drive connected successfully for user {current_user}")
        
        return GDriveCallbackResponse(
            success=True,
            message="Google Drive connected successfully",
            user_email=user_email
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth callback failed: {str(e)}"
        )


@router.delete("/disconnect", response_model=GDriveDisconnectResponse)
async def disconnect_gdrive(
    current_user: str = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Disconnect Google Drive and revoke access
    
    Revokes OAuth tokens and clears stored credentials.
    """
    logger.info(f"Google Drive disconnect request from user {current_user}")
    
    try:
        # Revoke access
        success = auth_service.revoke_access()
        
        if not success:
            logger.warning(f"Failed to revoke access for user {current_user}")
            return GDriveDisconnectResponse(
                success=False,
                message="Failed to revoke access. Tokens may have already been revoked."
            )
        
        logger.info(f"Google Drive disconnected for user {current_user}")
        
        return GDriveDisconnectResponse(
            success=True,
            message="Google Drive disconnected successfully"
        )
    
    except Exception as e:
        logger.error(f"Failed to disconnect Google Drive: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disconnect: {str(e)}"
        )


@router.get("/status", response_model=GDriveStatusResponse)
async def get_gdrive_status(
    current_user: str = Depends(get_current_user),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """
    Check Google Drive connection status
    
    Returns connection status and user information if connected.
    """
    logger.info(f"Google Drive status request from user {current_user}")
    
    try:
        # Check if authenticated
        is_authenticated = auth_service.is_authenticated()
        
        if not is_authenticated:
            return GDriveStatusResponse(
                connected=False,
                user_email=None,
                token_expiry=None,
                scopes=None
            )
        
        # Get token info
        token_info = auth_service.get_token_info()
        
        return GDriveStatusResponse(
            connected=True,
            user_email=token_info.get("user_email"),
            token_expiry=token_info.get("expiry"),
            scopes=token_info.get("scopes", [])
        )
    
    except Exception as e:
        logger.error(f"Failed to get Google Drive status: {e}", exc_info=True)
        # Return disconnected status on error
        return GDriveStatusResponse(
            connected=False,
            user_email=None,
            token_expiry=None,
            scopes=None
        )
