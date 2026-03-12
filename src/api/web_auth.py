"""Web application authentication endpoints with JWT tokens"""

import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()
security = HTTPBearer()

# Hardcoded credentials for local deployment
WEB_USERNAME = "girish"
WEB_PASSWORD = "Girish@123"

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


# ============================================================================
# Request/Response Models
# ============================================================================

class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    username: str


class LogoutResponse(BaseModel):
    """Logout response model"""
    success: bool
    message: str


class StatusResponse(BaseModel):
    """Authentication status response"""
    authenticated: bool
    username: Optional[str] = None
    expires_at: Optional[datetime] = None


# ============================================================================
# JWT Token Functions
# ============================================================================

def create_access_token(username: str) -> tuple[str, datetime]:
    """Create JWT access token"""
    expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    payload = {
        "sub": username,
        "exp": expires_at,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_at


def verify_token(token: str) -> Optional[str]:
    """Verify JWT token and return username"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        
        if username is None:
            return None
            
        return username
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.PyJWTError as e:
        logger.warning(f"Token validation failed: {e}")
        return None
    except Exception as e:
        logger.warning(f"Token validation failed: {e}")
        return None


# ============================================================================
# Authentication Dependency
# ============================================================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    username = verify_token(token)
    
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return username


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user with hardcoded credentials and return JWT token
    
    - **username**: Username (hardcoded: "girish")
    - **password**: Password (hardcoded: "Girish@123")
    """
    logger.info(f"Login attempt for user: {request.username}")
    
    # Validate credentials
    if request.username != WEB_USERNAME or request.password != WEB_PASSWORD:
        logger.warning(f"Failed login attempt for user: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token, expires_at = create_access_token(request.username)
    expires_in = int((expires_at - datetime.utcnow()).total_seconds())
    
    logger.info(f"User {request.username} logged in successfully")
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        username=request.username
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(current_user: str = Depends(get_current_user)):
    """
    Logout current user (client should discard token)
    
    Note: JWT tokens are stateless, so logout is handled client-side by discarding the token.
    This endpoint is provided for consistency and logging purposes.
    """
    logger.info(f"User {current_user} logged out")
    
    return LogoutResponse(
        success=True,
        message="Logged out successfully"
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Check authentication status
    
    Returns authentication status and user information if authenticated.
    """
    if credentials is None:
        return StatusResponse(authenticated=False)
    
    token = credentials.credentials
    username = verify_token(token)
    
    if username is None:
        return StatusResponse(authenticated=False)
    
    # Decode token to get expiration
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        expires_at = datetime.fromtimestamp(payload["exp"])
        
        return StatusResponse(
            authenticated=True,
            username=username,
            expires_at=expires_at
        )
    except:
        return StatusResponse(authenticated=False)
