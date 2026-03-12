"""
Access Control Module

This module provides role-based access control (RBAC) for the Excel RAG system.
It enforces file-level permissions, logs access attempts for audit, and supports
data masking for sensitive columns.

Key Components:
- AccessController: Main service for access control enforcement
- AccessControlStore: Database operations for access control entries
- AuditLogger: Logs all access attempts for compliance

Requirements: 29.1, 29.2, 29.3, 29.4, 29.5
"""

from src.access_control.controller import (
    AccessController,
    AccessControlConfig,
    AccessDeniedError,
)
from src.access_control.store import AccessControlStore
from src.access_control.audit_logger import AuditLogger

__all__ = [
    "AccessController",
    "AccessControlConfig",
    "AccessDeniedError",
    "AccessControlStore",
    "AuditLogger",
]
