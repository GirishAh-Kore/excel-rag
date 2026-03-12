"""Authentication API endpoints"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from src.api.models import (
    AuthLoginResponse,
    AuthCallbackRequest,
    AuthCallbackResponse,
    AuthStatusResponse,
    AuthLogoutResponse,
    ErrorResponse
)
from src.api.dependencies import get_auth_service, get_correlation_id
from src.auth.authentication_service import AuthenticationService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/login",
    response_model=AuthLoginResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Initiate OAuth flow",
    description="Initiates OAuth 2.0 flow with Google and returns authorization URL"
)
async def login(
    auth_service: AuthenticationService = Depends(get_auth_service),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Initiate OAuth 2.0 authentication flow.
    
    Returns an authorization URL that the user should visit to grant permissions.
    The state parameter is included for CSRF protection.
    """
    try:
        logger.info(f"Initiating OAuth flow", extra={'correlation_id': correlation_id})
        
        # Generate authorization URL
        auth_url, state = auth_service.initiate_oauth_flow()
        
        logger.info(
            f"OAuth flow initiated successfully",
            extra={'correlation_id': correlation_id, 'state': state}
        )
        
        return AuthLoginResponse(
            authorization_url=auth_url,
            state=state
        )
        
    except Exception as e:
        logger.error(
            f"Failed to initiate OAuth flow: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate authentication: {str(e)}"
        )


@router.get(
    "/callback",
    response_model=AuthCallbackResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Authentication failed"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Handle OAuth callback",
    description="Handles OAuth callback and exchanges authorization code for tokens"
)
async def callback(
    code: str = Query(..., description="Authorization code from OAuth callback"),
    state: str = Query(..., description="State parameter for CSRF validation"),
    auth_service: AuthenticationService = Depends(get_auth_service),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Handle OAuth 2.0 callback.
    
    Exchanges the authorization code for access and refresh tokens.
    Validates the state parameter for CSRF protection.
    """
    try:
        logger.info(
            f"Handling OAuth callback",
            extra={'correlation_id': correlation_id, 'state': state}
        )
        
        # Validate inputs
        if not code or not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing code or state parameter"
            )
        
        # Handle callback and exchange code for tokens
        success = auth_service.handle_oauth_callback(code, state)
        
        if success:
            logger.info(
                f"OAuth callback handled successfully",
                extra={'correlation_id': correlation_id}
            )
            return AuthCallbackResponse(
                success=True,
                message="Authentication successful"
            )
        else:
            logger.warning(
                f"OAuth callback failed",
                extra={'correlation_id': correlation_id}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed. Please try again."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error handling OAuth callback: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete authentication: {str(e)}"
        )


@router.post(
    "/logout",
    response_model=AuthLogoutResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Logout and revoke access",
    description="Revokes access tokens and clears stored credentials"
)
async def logout(
    auth_service: AuthenticationService = Depends(get_auth_service),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Logout and revoke access.
    
    Revokes the access token with Google and clears all stored credentials.
    """
    try:
        logger.info(f"Logging out user", extra={'correlation_id': correlation_id})
        
        # Revoke access
        success = auth_service.revoke_access()
        
        if success:
            logger.info(
                f"User logged out successfully",
                extra={'correlation_id': correlation_id}
            )
            return AuthLogoutResponse(
                success=True,
                message="Logged out successfully"
            )
        else:
            logger.warning(
                f"Logout failed or user was not authenticated",
                extra={'correlation_id': correlation_id}
            )
            return AuthLogoutResponse(
                success=False,
                message="No active session to logout"
            )
            
    except Exception as e:
        logger.error(
            f"Error during logout: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to logout: {str(e)}"
        )


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    responses={
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Check authentication status",
    description="Checks if user is authenticated and returns token expiry information"
)
async def status(
    auth_service: AuthenticationService = Depends(get_auth_service),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Check authentication status.
    
    Returns whether the user is authenticated, token expiry time, and user email.
    """
    try:
        logger.debug(
            f"Checking authentication status",
            extra={'correlation_id': correlation_id}
        )
        
        # Check if authenticated
        is_authenticated = auth_service.is_authenticated()
        
        if is_authenticated:
            # Get token info
            token_info = auth_service.get_token_info()
            
            return AuthStatusResponse(
                authenticated=True,
                token_expiry=token_info.get('expiry'),
                user_email=token_info.get('email')
            )
        else:
            return AuthStatusResponse(
                authenticated=False,
                token_expiry=None,
                user_email=None
            )
            
    except Exception as e:
        logger.error(
            f"Error checking authentication status: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check authentication status: {str(e)}"
        )
