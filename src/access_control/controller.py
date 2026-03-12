"""
Access Controller

This module provides the main AccessController service for role-based
access control (RBAC) in the Excel RAG system. It enforces file-level
permissions, logs access attempts, and supports data masking.

Key Features:
- Role-based access control: admin, developer, analyst, viewer
- File-level access restrictions
- Audit logging for all access attempts
- Data masking for sensitive columns
- All dependencies injected via constructor (DIP compliant)

Requirements: 29.1, 29.2, 29.3, 29.4, 29.5
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from src.access_control.audit_logger import AuditLogger
from src.access_control.store import AccessControlStore
from src.exceptions import RAGSystemError
from src.models.enterprise import UserRole

logger = logging.getLogger(__name__)


# Role hierarchy: higher roles include permissions of lower roles
ROLE_HIERARCHY: Dict[UserRole, int] = {
    UserRole.VIEWER: 1,
    UserRole.ANALYST: 2,
    UserRole.DEVELOPER: 3,
    UserRole.ADMIN: 4,
}

# Minimum role required for each action
ACTION_REQUIRED_ROLES: Dict[str, UserRole] = {
    "view": UserRole.VIEWER,
    "search": UserRole.ANALYST,
    "export": UserRole.ANALYST,
}

# Default mask pattern for sensitive data
DEFAULT_MASK = "***MASKED***"


class AccessDeniedError(RAGSystemError):
    """
    Raised when access is denied to a protected resource.
    
    This exception should result in a 403 Forbidden HTTP response.
    
    Requirements: 29.3
    """
    
    def __init__(
        self,
        message: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> None:
        """
        Initialize AccessDeniedError.
        
        Args:
            message: Human-readable error message.
            user_id: ID of the user who was denied.
            resource_type: Type of resource (chunk, file, trace).
            resource_id: ID of the resource.
            action: Action that was denied.
        """
        super().__init__(
            message,
            details={
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
            }
        )
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action


@dataclass
class AccessControlConfig:
    """
    Configuration for AccessController.
    
    Attributes:
        enable_access_control: Whether to enforce access control.
        default_role: Default role for users without explicit assignment.
        sensitive_column_patterns: Regex patterns for sensitive columns.
        mask_pattern: Pattern to use for masking sensitive data.
        allow_anonymous: Whether to allow anonymous access (viewer only).
    """
    enable_access_control: bool = True
    default_role: Optional[UserRole] = None
    sensitive_column_patterns: List[str] = field(default_factory=lambda: [
        r"(?i)ssn",
        r"(?i)social.?security",
        r"(?i)password",
        r"(?i)secret",
        r"(?i)credit.?card",
        r"(?i)card.?number",
        r"(?i)cvv",
        r"(?i)pin",
        r"(?i)salary",
        r"(?i)compensation",
    ])
    mask_pattern: str = DEFAULT_MASK
    allow_anonymous: bool = False


class AccessController:
    """
    Main service for role-based access control.
    
    Enforces file-level permissions, logs access attempts for audit,
    and supports data masking for sensitive columns.
    
    Role Hierarchy (higher includes lower):
    - ADMIN: Full access to all features and data
    - DEVELOPER: Access to debugging tools and chunk visibility
    - ANALYST: Access to query features and data analysis
    - VIEWER: Read-only access to query results
    
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        store: Access control store for permission queries.
        audit_logger: Logger for access attempts.
        config: Configuration settings.
    
    Requirements: 29.1, 29.2, 29.3, 29.4, 29.5
    """
    
    def __init__(
        self,
        store: AccessControlStore,
        audit_logger: AuditLogger,
        config: Optional[AccessControlConfig] = None,
    ) -> None:
        """
        Initialize the AccessController.
        
        Args:
            store: Access control store for permission queries.
            audit_logger: Logger for access attempts.
            config: Optional configuration settings.
        
        Raises:
            RAGSystemError: If required dependencies are None.
        """
        if store is None:
            raise RAGSystemError(
                "store is required",
                details={"parameter": "store"}
            )
        if audit_logger is None:
            raise RAGSystemError(
                "audit_logger is required",
                details={"parameter": "audit_logger"}
            )
        
        self.store = store
        self.audit_logger = audit_logger
        self.config = config or AccessControlConfig()
        
        # Compile sensitive column patterns
        self._sensitive_patterns: List[re.Pattern] = [
            re.compile(pattern)
            for pattern in self.config.sensitive_column_patterns
        ]
        
        logger.info(
            f"AccessController initialized "
            f"(enabled={self.config.enable_access_control})"
        )

    def check_access(
        self,
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Check if a user has access to a resource and log the attempt.
        
        This method checks permissions and logs the access attempt.
        Use this when you want to handle denied access yourself.
        
        Args:
            user_id: ID of the user (None for anonymous).
            resource_type: Type of resource (chunk, file, trace).
            resource_id: ID of the specific resource.
            action: Action being attempted (view, search, export).
            ip_address: Optional IP address for audit logging.
        
        Returns:
            True if access is granted, False otherwise.
        
        Requirements: 29.1, 29.2, 29.4
        """
        # If access control is disabled, allow all
        if not self.config.enable_access_control:
            return True
        
        # Handle anonymous users
        if not user_id:
            if self.config.allow_anonymous:
                user_id = "anonymous"
            else:
                self._log_access(
                    user_id="anonymous",
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    access_granted=False,
                    ip_address=ip_address,
                )
                return False
        
        # Get user's effective role
        effective_role = self._get_effective_role(user_id, resource_id)
        
        if effective_role is None:
            self._log_access(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                access_granted=False,
                ip_address=ip_address,
            )
            return False
        
        # Check if role is sufficient for the action
        required_role = ACTION_REQUIRED_ROLES.get(action, UserRole.VIEWER)
        access_granted = self._role_has_permission(effective_role, required_role)
        
        # Log the access attempt
        self._log_access(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            access_granted=access_granted,
            ip_address=ip_address,
        )
        
        return access_granted

    def require_access(
        self,
        user_id: Optional[str],
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Require access to a resource, raising AccessDeniedError if denied.
        
        Use this method when you want to enforce access control and
        have the error propagate to return a 403 Forbidden response.
        
        Args:
            user_id: ID of the user (None for anonymous).
            resource_type: Type of resource (chunk, file, trace).
            resource_id: ID of the specific resource.
            action: Action being attempted (view, search, export).
            ip_address: Optional IP address for audit logging.
        
        Raises:
            AccessDeniedError: If access is denied (403 Forbidden).
        
        Requirements: 29.3
        """
        if not self.check_access(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            ip_address=ip_address,
        ):
            raise AccessDeniedError(
                message=f"Access denied to {resource_type}/{resource_id}",
                user_id=user_id or "anonymous",
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
            )
    
    def get_user_role(
        self,
        user_id: str,
        file_id: Optional[str] = None,
    ) -> Optional[UserRole]:
        """
        Get the user's role, optionally for a specific file.
        
        Args:
            user_id: ID of the user.
            file_id: Optional file ID for file-specific role.
        
        Returns:
            User's role or None if no role assigned.
        """
        if not user_id:
            return None
        
        return self._get_effective_role(user_id, file_id)
    
    def is_admin(self, user_id: str) -> bool:
        """
        Check if a user has admin role.
        
        Args:
            user_id: ID of the user.
        
        Returns:
            True if user is an admin.
        """
        role = self._get_effective_role(user_id, None)
        return role == UserRole.ADMIN

    def mask_sensitive_data(
        self,
        data: Dict[str, Any],
        user_role: Optional[UserRole] = None,
    ) -> Dict[str, Any]:
        """
        Mask sensitive columns in data based on user role.
        
        Admins and developers see all data. Analysts and viewers
        have sensitive columns masked.
        
        Args:
            data: Dictionary of column names to values.
            user_role: User's role (None masks all sensitive data).
        
        Returns:
            Data with sensitive columns masked if applicable.
        
        Requirements: 29.5
        """
        # Admins and developers see all data
        if user_role in (UserRole.ADMIN, UserRole.DEVELOPER):
            return data
        
        masked_data = {}
        for column, value in data.items():
            if self._is_sensitive_column(column):
                masked_data[column] = self.config.mask_pattern
            else:
                masked_data[column] = value
        
        return masked_data
    
    def mask_sensitive_rows(
        self,
        rows: List[Dict[str, Any]],
        user_role: Optional[UserRole] = None,
    ) -> List[Dict[str, Any]]:
        """
        Mask sensitive columns in a list of rows.
        
        Args:
            rows: List of row dictionaries.
            user_role: User's role.
        
        Returns:
            Rows with sensitive columns masked if applicable.
        
        Requirements: 29.5
        """
        return [self.mask_sensitive_data(row, user_role) for row in rows]
    
    def get_sensitive_columns(
        self,
        columns: List[str],
    ) -> Set[str]:
        """
        Identify which columns are sensitive.
        
        Args:
            columns: List of column names to check.
        
        Returns:
            Set of column names that are sensitive.
        """
        return {col for col in columns if self._is_sensitive_column(col)}

    def _get_effective_role(
        self,
        user_id: str,
        file_id: Optional[str],
    ) -> Optional[UserRole]:
        """
        Get the effective role for a user, considering hierarchy.
        
        Checks in order:
        1. File-specific role (if file_id provided)
        2. Global role (file_id = '*')
        3. Default role from config
        
        Args:
            user_id: ID of the user.
            file_id: Optional file ID for file-specific role.
        
        Returns:
            Effective role or None.
        """
        # Check file-specific role first
        if file_id:
            file_role = self.store.get_user_role_for_file(user_id, file_id)
            if file_role:
                return file_role
        
        # Check global role
        global_role = self.store.get_user_global_role(user_id)
        if global_role:
            return global_role
        
        # Fall back to default role
        return self.config.default_role
    
    def _role_has_permission(
        self,
        user_role: UserRole,
        required_role: UserRole,
    ) -> bool:
        """
        Check if a user role has sufficient permission.
        
        Higher roles include permissions of lower roles.
        
        Args:
            user_role: The user's role.
            required_role: The minimum required role.
        
        Returns:
            True if user_role >= required_role in hierarchy.
        """
        user_level = ROLE_HIERARCHY.get(user_role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level
    
    def _is_sensitive_column(self, column_name: str) -> bool:
        """
        Check if a column name matches sensitive patterns.
        
        Args:
            column_name: Name of the column to check.
        
        Returns:
            True if column matches any sensitive pattern.
        """
        for pattern in self._sensitive_patterns:
            if pattern.search(column_name):
                return True
        return False
    
    def _log_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        access_granted: bool,
        ip_address: Optional[str],
    ) -> None:
        """
        Log an access attempt.
        
        Catches and logs any errors from the audit logger to avoid
        failing the main operation due to logging issues.
        """
        try:
            self.audit_logger.log_access(
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                access_granted=access_granted,
                ip_address=ip_address,
            )
        except Exception as e:
            # Don't fail the main operation due to logging issues
            logger.error(f"Failed to log access attempt: {e}")
