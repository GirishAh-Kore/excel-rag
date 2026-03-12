"""
Template Store Module.

This module implements storage for query templates using the SQLite database.

Supports Requirements 25.1, 25.4, 25.5.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from src.database.connection import DatabaseConnection
from src.models.enterprise import QueryTemplate

logger = logging.getLogger(__name__)


class TemplateStore:
    """
    Storage for query templates.
    
    Provides persistence for query templates, supporting CRUD operations
    and organization-based sharing.
    
    All dependencies are injected via constructor following DIP.
    
    Example:
        >>> store = TemplateStore(db=database_connection)
        >>> store.create_template(template)
        >>> templates = store.get_templates_for_user("user_123")
    """
    
    # SQL statements
    CREATE_TEMPLATE_SQL = """
        INSERT INTO query_templates 
        (template_id, name, template_text, parameters, created_by, organization_id, is_shared, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    GET_TEMPLATE_SQL = """
        SELECT template_id, name, template_text, parameters, created_by, 
               organization_id, is_shared, created_at
        FROM query_templates
        WHERE template_id = ?
    """
    
    GET_USER_TEMPLATES_SQL = """
        SELECT template_id, name, template_text, parameters, created_by,
               organization_id, is_shared, created_at
        FROM query_templates
        WHERE created_by = ?
        ORDER BY created_at DESC
    """
    
    GET_USER_AND_SHARED_TEMPLATES_SQL = """
        SELECT template_id, name, template_text, parameters, created_by,
               organization_id, is_shared, created_at
        FROM query_templates
        WHERE created_by = ? 
           OR (is_shared = 1 AND organization_id = ?)
        ORDER BY created_at DESC
    """
    
    UPDATE_TEMPLATE_SQL = """
        UPDATE query_templates
        SET name = ?, template_text = ?, parameters = ?, is_shared = ?, updated_at = ?
        WHERE template_id = ?
    """
    
    DELETE_TEMPLATE_SQL = """
        DELETE FROM query_templates
        WHERE template_id = ?
    """
    
    def __init__(self, db: DatabaseConnection) -> None:
        """
        Initialize TemplateStore with database connection.
        
        Args:
            db: Database connection for persistence.
            
        Raises:
            ValueError: If db is None.
        """
        if db is None:
            raise ValueError("db is required")
        
        self._db = db
        
        logger.info("TemplateStore initialized")
    
    def create_template(self, template: QueryTemplate) -> bool:
        """
        Create a new template.
        
        Args:
            template: QueryTemplate to create.
            
        Returns:
            True if created successfully.
        """
        try:
            parameters_json = json.dumps(template.parameters)
            
            self._db.execute_insert(
                self.CREATE_TEMPLATE_SQL,
                (
                    template.template_id,
                    template.name,
                    template.template_text,
                    parameters_json,
                    template.created_by,
                    None,  # organization_id - not in model yet
                    1 if template.is_shared else 0,
                    template.created_at.isoformat()
                )
            )
            
            logger.debug(f"Created template: {template.template_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create template {template.template_id}: {e}")
            return False
    
    def get_template(self, template_id: str) -> Optional[QueryTemplate]:
        """
        Get template by ID.
        
        Args:
            template_id: Unique template identifier.
            
        Returns:
            QueryTemplate if found, None otherwise.
        """
        try:
            rows = self._db.execute_query(
                self.GET_TEMPLATE_SQL,
                (template_id,)
            )
            
            if not rows:
                return None
            
            return self._row_to_template(rows[0])
            
        except Exception as e:
            logger.error(f"Failed to get template {template_id}: {e}")
            return None
    
    def get_templates_for_user(
        self,
        user_id: str,
        organization_id: Optional[str] = None,
        include_shared: bool = True
    ) -> list[QueryTemplate]:
        """
        Get templates accessible to a user.
        
        Args:
            user_id: User ID to get templates for.
            organization_id: Optional organization ID for shared templates.
            include_shared: Whether to include shared templates.
            
        Returns:
            List of accessible QueryTemplate objects.
        """
        try:
            if include_shared and organization_id:
                rows = self._db.execute_query(
                    self.GET_USER_AND_SHARED_TEMPLATES_SQL,
                    (user_id, organization_id)
                )
            else:
                rows = self._db.execute_query(
                    self.GET_USER_TEMPLATES_SQL,
                    (user_id,)
                )
            
            return [self._row_to_template(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Failed to get templates for user {user_id}: {e}")
            return []
    
    def update_template(self, template: QueryTemplate) -> bool:
        """
        Update an existing template.
        
        Args:
            template: QueryTemplate with updated values.
            
        Returns:
            True if updated successfully.
        """
        try:
            parameters_json = json.dumps(template.parameters)
            now = datetime.utcnow().isoformat()
            
            rows_affected = self._db.execute_update(
                self.UPDATE_TEMPLATE_SQL,
                (
                    template.name,
                    template.template_text,
                    parameters_json,
                    1 if template.is_shared else 0,
                    now,
                    template.template_id
                )
            )
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Failed to update template {template.template_id}: {e}")
            return False
    
    def delete_template(self, template_id: str) -> bool:
        """
        Delete a template.
        
        Args:
            template_id: ID of the template to delete.
            
        Returns:
            True if deleted successfully.
        """
        try:
            rows_affected = self._db.execute_update(
                self.DELETE_TEMPLATE_SQL,
                (template_id,)
            )
            
            return rows_affected > 0
            
        except Exception as e:
            logger.error(f"Failed to delete template {template_id}: {e}")
            return False
    
    def _row_to_template(self, row) -> QueryTemplate:
        """Convert database row to QueryTemplate."""
        parameters = json.loads(row["parameters"]) if row["parameters"] else []
        
        # Parse created_at timestamp
        created_at_str = row["created_at"]
        if isinstance(created_at_str, str):
            # Handle ISO format
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        else:
            created_at = created_at_str
        
        return QueryTemplate(
            template_id=row["template_id"],
            name=row["name"],
            template_text=row["template_text"],
            parameters=parameters,
            created_by=row["created_by"],
            created_at=created_at,
            is_shared=bool(row["is_shared"])
        )
