"""
Audit Logger for Access Control

This module provides audit logging for all access attempts to protected
resources. It records access attempts for compliance and security auditing.

Key Features:
- Log all access attempts (granted and denied)
- Support for resource types: chunk, file, trace
- Support for actions: view, search, export
- Query audit logs by user, resource, or time range

Requirements: 29.4
"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from src.database.connection import DatabaseConnection
from src.exceptions import RAGSystemError
from src.models.enterprise import AccessAuditLog

logger = logging.getLogger(__name__)


class AuditLoggerError(RAGSystemError):
    """Errors related to audit logging operations."""
    pass


class AuditLogger:
    """
    Logs all access attempts for audit and compliance.
    
    Records both successful and denied access attempts to protected
    resources, enabling security auditing and compliance reporting.
    
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        db: Database connection for persistence operations.
    
    Requirements: 29.4
    """
    
    def __init__(self, db: DatabaseConnection) -> None:
        """
        Initialize the AuditLogger.
        
        Args:
            db: Database connection instance.
        
        Raises:
            AuditLoggerError: If db is None.
        """
        if db is None:
            raise AuditLoggerError(
                "db is required",
                details={"parameter": "db"}
            )
        self.db = db
        logger.info("AuditLogger initialized")
    
    def log_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        access_granted: bool,
        ip_address: Optional[str] = None,
    ) -> AccessAuditLog:
        """
        Log an access attempt.
        
        Args:
            user_id: ID of the user attempting access.
            resource_type: Type of resource (chunk, file, trace).
            resource_id: ID of the specific resource.
            action: Action attempted (view, search, export).
            access_granted: Whether access was granted.
            ip_address: Optional IP address of the requester.
        
        Returns:
            Created AccessAuditLog entry.
        
        Raises:
            AuditLoggerError: If logging fails.
        """
        try:
            log_id = f"log_{uuid.uuid4().hex[:12]}"
            timestamp = datetime.utcnow()
            
            # Create the audit log entry (validates fields)
            audit_log = AccessAuditLog(
                log_id=log_id,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                access_granted=access_granted,
                timestamp=timestamp,
                ip_address=ip_address,
            )
            
            # Persist to database
            query = """
                INSERT INTO access_audit_log
                (log_id, user_id, resource_type, resource_id, action,
                 access_granted, timestamp, ip_address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.db.execute_insert(
                query,
                (
                    audit_log.log_id,
                    audit_log.user_id,
                    audit_log.resource_type,
                    audit_log.resource_id,
                    audit_log.action,
                    audit_log.access_granted,
                    audit_log.timestamp,
                    audit_log.ip_address,
                )
            )
            
            log_level = logging.INFO if access_granted else logging.WARNING
            logger.log(
                log_level,
                f"Access {'granted' if access_granted else 'denied'}: "
                f"user={user_id}, resource={resource_type}/{resource_id}, "
                f"action={action}"
            )
            
            return audit_log
            
        except ValueError as e:
            # Re-raise validation errors from AccessAuditLog
            raise AuditLoggerError(
                f"Invalid audit log parameters: {e}",
                details={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "action": action,
                }
            )
        except Exception as e:
            logger.error(f"Failed to log access attempt: {e}")
            raise AuditLoggerError(
                f"Failed to log access attempt: {e}",
                details={"user_id": user_id, "resource_id": resource_id}
            )

    def get_logs_for_user(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[AccessAuditLog]:
        """
        Get audit logs for a specific user.
        
        Args:
            user_id: ID of the user.
            limit: Maximum number of logs to return.
        
        Returns:
            List of AccessAuditLog entries, most recent first.
        
        Raises:
            AuditLoggerError: If query fails.
        """
        if not user_id:
            return []
        
        try:
            query = """
                SELECT log_id, user_id, resource_type, resource_id,
                       action, access_granted, timestamp, ip_address
                FROM access_audit_log
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            results = self.db.execute_query(query, (user_id, limit))
            return self._rows_to_audit_logs(results)
            
        except Exception as e:
            logger.error(f"Failed to get logs for user: {e}")
            raise AuditLoggerError(
                f"Failed to get logs for user: {e}",
                details={"user_id": user_id}
            )
    
    def get_logs_for_resource(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100,
    ) -> List[AccessAuditLog]:
        """
        Get audit logs for a specific resource.
        
        Args:
            resource_type: Type of resource (chunk, file, trace).
            resource_id: ID of the resource.
            limit: Maximum number of logs to return.
        
        Returns:
            List of AccessAuditLog entries, most recent first.
        
        Raises:
            AuditLoggerError: If query fails.
        """
        if not resource_type or not resource_id:
            return []
        
        try:
            query = """
                SELECT log_id, user_id, resource_type, resource_id,
                       action, access_granted, timestamp, ip_address
                FROM access_audit_log
                WHERE resource_type = ? AND resource_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            results = self.db.execute_query(
                query, (resource_type, resource_id, limit)
            )
            return self._rows_to_audit_logs(results)
            
        except Exception as e:
            logger.error(f"Failed to get logs for resource: {e}")
            raise AuditLoggerError(
                f"Failed to get logs for resource: {e}",
                details={
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                }
            )
    
    def get_denied_access_logs(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AccessAuditLog]:
        """
        Get logs of denied access attempts.
        
        Useful for security monitoring and detecting unauthorized
        access attempts.
        
        Args:
            since: Optional start time for filtering.
            limit: Maximum number of logs to return.
        
        Returns:
            List of AccessAuditLog entries for denied access.
        
        Raises:
            AuditLoggerError: If query fails.
        """
        try:
            if since:
                query = """
                    SELECT log_id, user_id, resource_type, resource_id,
                           action, access_granted, timestamp, ip_address
                    FROM access_audit_log
                    WHERE access_granted = 0 AND timestamp >= ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                results = self.db.execute_query(query, (since, limit))
            else:
                query = """
                    SELECT log_id, user_id, resource_type, resource_id,
                           action, access_granted, timestamp, ip_address
                    FROM access_audit_log
                    WHERE access_granted = 0
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                results = self.db.execute_query(query, (limit,))
            
            return self._rows_to_audit_logs(results)
            
        except Exception as e:
            logger.error(f"Failed to get denied access logs: {e}")
            raise AuditLoggerError(
                f"Failed to get denied access logs: {e}",
                details={"since": since}
            )
    
    def _rows_to_audit_logs(self, rows: list) -> List[AccessAuditLog]:
        """Convert database rows to AccessAuditLog objects."""
        logs = []
        for row in rows:
            timestamp = row["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            logs.append(AccessAuditLog(
                log_id=row["log_id"],
                user_id=row["user_id"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                action=row["action"],
                access_granted=bool(row["access_granted"]),
                timestamp=timestamp,
                ip_address=row["ip_address"],
            ))
        return logs
