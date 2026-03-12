"""Middleware components for API"""

import time
import logging
import uuid
from typing import Callable
from contextvars import ContextVar
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Context variable for correlation ID
correlation_id_var: ContextVar[str] = ContextVar('correlation_id', default='')


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to all requests"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get('X-Correlation-ID', str(uuid.uuid4()))
        
        # Set in context variable for logging
        correlation_id_var.set(correlation_id)
        
        # Process request
        response = await call_next(request)
        
        # Add correlation ID to response headers
        response.headers['X-Correlation-ID'] = correlation_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all API requests and responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Start timer
        start_time = time.time()
        
        # Get correlation ID from context
        correlation_id = correlation_id_var.get()
        
        # Log request
        logger.info(
            f"Request started",
            extra={
                'correlation_id': correlation_id,
                'method': request.method,
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'client_host': request.client.host if request.client else None
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            logger.info(
                f"Request completed",
                extra={
                    'correlation_id': correlation_id,
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'duration_ms': duration_ms
                }
            )
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"Request failed",
                extra={
                    'correlation_id': correlation_id,
                    'method': request.method,
                    'path': request.url.path,
                    'duration_ms': duration_ms,
                    'error': str(e)
                },
                exc_info=True
            )
            
            raise


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware with per-endpoint limits"""
    
    def __init__(self, app: ASGIApp, default_requests_per_minute: int = 60):
        super().__init__(app)
        self.default_requests_per_minute = default_requests_per_minute
        self.request_counts: dict = {}  # {(client_ip, endpoint): [(timestamp, count)]}
        
        # Per-endpoint rate limits
        self.endpoint_limits = {
            '/api/v1/query': 10,  # 10 queries per minute
            '/api/v1/index/full': 1,  # 1 full index per minute
            '/api/v1/index/incremental': 1,  # 1 incremental index per minute
        }
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get client IP and endpoint
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        key = (client_ip, endpoint)
        
        # Get rate limit for this endpoint
        requests_per_minute = self.endpoint_limits.get(endpoint, self.default_requests_per_minute)
        
        # Get current timestamp
        current_time = time.time()
        
        # Clean old entries (older than 1 minute)
        if key in self.request_counts:
            self.request_counts[key] = [
                (ts, count) for ts, count in self.request_counts[key]
                if current_time - ts < 60
            ]
        
        # Count requests in last minute
        if key not in self.request_counts:
            self.request_counts[key] = []
        
        request_count = sum(count for _, count in self.request_counts[key])
        
        # Check rate limit
        if request_count >= requests_per_minute:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {requests_per_minute} requests per minute for this endpoint."
            )
        
        # Add current request
        self.request_counts[key].append((current_time, 1))
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers['X-RateLimit-Limit'] = str(requests_per_minute)
        response.headers['X-RateLimit-Remaining'] = str(requests_per_minute - request_count - 1)
        
        return response


def get_correlation_id() -> str:
    """Get correlation ID from context"""
    return correlation_id_var.get()
