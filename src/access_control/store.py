"""
Access Control Store

This module provides database operations for access control entries.
It handles CRUD operations for file-level access permissions and
supports querying user permissions efficiently.

Key Features:
- Store and retrieve access control entries
- Query permissions by user or file
- Support for role-based access control
- All dependencies injected via constructor (DIP compliant)

Requirements: 29.1, 29.2
"""

import logging
from datetime import datetime
from typing import List, Optional

from src.database.connection import DatabaseConnection
from src.exceptions import RAGSystemError
from src.models.enterprise import AccessControlEntry, UserRole

logger = logging.getLogger(__name__)


class AccessControlStoreError(RAGSystemError):
    """Errors related to access control storage operations."""
    pass


class AccessControlStore:
    """
    Database operations for access control entries.
    
    Provides CRUD operations for file-level access permissions,
    supporting role-based access control queries.
    
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        db: Database connection for persistence operations.
    
    Requirements: 29.1, 29.2
    """
    
    def __init__(self, db: DatabaseConnection) -> None:
        """
        Initialize the AccessControlStore.
        
        Args:
            db: Database connection instance.
        
        Raises:
            AccessControlStoreError: If db is None.
        """
        if db is None:
            raise AccessControlStoreError(
                "db is required",
                details={"parameter": "db"}
            )
        self.db = db
        logger.info("AccessControlStore initialized")
    
    def get_user_role_for_file(
        self,
        user_id: str,
        file_id: str,
    ) -> Optional[UserRole]:
        """
        Get the user's role for a specific file.
        
        Args:
            user_id: ID of the user.
            file_id: ID of the file.
        
        Returns:
            UserRole if access entry exists, None otherwise.
        
        Raises:
            AccessControlStoreError: If query fails.
        """
        if not user_id or not file_id:
            return None
        
        try:
            query = """
                SELECT role FROM file_access_control
                WHERE user_id = ? AND file_id = ?
            """
            results = self.db.execute_query(query, (user_id, file_id))
            
            if results and results[0]["role"]:
                role_str = results[0]["role"]
                return UserRole(role_str)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user role for file: {e}")
            raise AccessControlStoreError(
                f"Failed to get user role: {e}",
                details={"user_id": user_id, "file_id": file_id}
            )

    def get_user_global_role(self, user_id: str) -> Optional[UserRole]:
        """
        Get the user's global role (not file-specific).
        
        Global roles are stored with file_id = '*'.
        
        Args:
            user_id: ID of the user.
        
        Returns:
            UserRole if global role exists, None otherwise.
        """
        return self.get_user_role_for_file(user_id, "*")
    
    def get_accessible_files(self, user_id: str) -> List[str]:
        """
        Get list of file IDs the user has access to.
        
        Args:
            user_id: ID of the user.
        
        Returns:
            List of file IDs the user can access.
        
        Raises:
            AccessControlStoreError: If query fails.
        """
        if not user_id:
            return []
        
        try:
            query = """
                SELECT file_id FROM file_access_control
                WHERE user_id = ? AND file_id != '*'
            """
            results = self.db.execute_query(query, (user_id,))
            return [row["file_id"] for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get accessible files: {e}")
            raise AccessControlStoreError(
                f"Failed to get accessible files: {e}",
                details={"user_id": user_id}
            )
    
    def grant_access(
        self,
        file_id: str,
        user_id: str,
        role: UserRole,
        granted_by: str,
    ) -> AccessControlEntry:
        """
        Grant access to a file for a user.
        
        Args:
            file_id: ID of the file (or '*' for global).
            user_id: ID of the user to grant access.
            role: Role to assign.
            granted_by: ID of the admin granting access.
        
        Returns:
            Created AccessControlEntry.
        
        Raises:
            AccessControlStoreError: If insert fails.
        """
        if not file_id or not user_id or not granted_by:
            raise AccessControlStoreError(
                "file_id, user_id, and granted_by are required",
                details={"file_id": file_id, "user_id": user_id}
            )
        
        try:
            granted_at = datetime.utcnow()
            
            # Use INSERT OR REPLACE to handle updates
            query = """
                INSERT OR REPLACE INTO file_access_control
                (file_id, user_id, role, granted_at, granted_by)
                VALUES (?, ?, ?, ?, ?)
            """
            self.db.execute_insert(
                query,
                (file_id, user_id, role.value, granted_at, granted_by)
            )
            
            logger.info(
                f"Granted {role.value} access to user {user_id} "
                f"for file {file_id}"
            )
            
            return AccessControlEntry(
                file_id=file_id,
                user_id=user_id,
                role=role,
                granted_at=granted_at,
                granted_by=granted_by,
            )
            
        except Exception as e:
            logger.error(f"Failed to grant access: {e}")
            raise AccessControlStoreError(
                f"Failed to grant access: {e}",
                details={"file_id": file_id, "user_id": user_id}
            )

    def revoke_access(self, file_id: str, user_id: str) -> bool:
        """
        Revoke access to a file for a user.
        
        Args:
            file_id: ID of the file.
            user_id: ID of the user.
        
        Returns:
            True if access was revoked, False if no entry existed.
        
        Raises:
            AccessControlStoreError: If delete fails.
        """
        if not file_id or not user_id:
            return False
        
        try:
            query = """
                DELETE FROM file_access_control
                WHERE file_id = ? AND user_id = ?
            """
            rows_affected = self.db.execute_update(query, (file_id, user_id))
            
            if rows_affected > 0:
                logger.info(
                    f"Revoked access for user {user_id} to file {file_id}"
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to revoke access: {e}")
            raise AccessControlStoreError(
                f"Failed to revoke access: {e}",
                details={"file_id": file_id, "user_id": user_id}
            )
    
    def get_file_access_entries(
        self,
        file_id: str,
    ) -> List[AccessControlEntry]:
        """
        Get all access entries for a file.
        
        Args:
            file_id: ID of the file.
        
        Returns:
            List of AccessControlEntry objects.
        
        Raises:
            AccessControlStoreError: If query fails.
        """
        if not file_id:
            return []
        
        try:
            query = """
                SELECT file_id, user_id, role, granted_at, granted_by
                FROM file_access_control
                WHERE file_id = ?
            """
            results = self.db.execute_query(query, (file_id,))
            
            entries = []
            for row in results:
                entries.append(AccessControlEntry(
                    file_id=row["file_id"],
                    user_id=row["user_id"],
                    role=UserRole(row["role"]),
                    granted_at=datetime.fromisoformat(row["granted_at"]),
                    granted_by=row["granted_by"],
                ))
            
            return entries
            
        except Exception as e:
            logger.error(f"Failed to get file access entries: {e}")
            raise AccessControlStoreError(
                f"Failed to get file access entries: {e}",
                details={"file_id": file_id}
            )
