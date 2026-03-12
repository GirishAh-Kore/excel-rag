"""
Template Manager Module.

This module implements query template management for creating, storing,
and executing parameterized query templates.

Key Features:
- Support parameterized templates with {{parameter_name}} syntax
- Extract parameters from template text
- Execute templates with parameter substitution
- Support template sharing within organization

Supports Requirements 25.1, 25.2, 25.3, 25.4, 25.5.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol, Union, runtime_checkable

from src.exceptions import TemplateError
from src.models.enterprise import QueryTemplate
from src.models.query_pipeline import ClarificationRequest, QueryResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# Regex pattern for template parameters: {{parameter_name}}
PARAMETER_PATTERN = re.compile(r'\{\{([a-zA-Z_][a-zA-Z0-9_]*)\}\}')

# Maximum template name length
MAX_TEMPLATE_NAME_LENGTH = 255

# Maximum template text length
MAX_TEMPLATE_TEXT_LENGTH = 10000


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class QueryExecutorProtocol(Protocol):
    """
    Protocol for query execution.
    
    Implementations must provide a method to process queries.
    """
    
    def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        file_hints: Optional[list[str]] = None,
        sheet_hints: Optional[list[str]] = None
    ) -> Union[QueryResponse, ClarificationRequest]:
        """Process a single query."""
        ...


@runtime_checkable
class TemplateStoreProtocol(Protocol):
    """
    Protocol for template storage.
    
    Implementations must provide methods for CRUD operations on templates.
    """
    
    def create_template(self, template: QueryTemplate) -> bool:
        """Create a new template."""
        ...
    
    def get_template(self, template_id: str) -> Optional[QueryTemplate]:
        """Get template by ID."""
        ...
    
    def get_templates_for_user(
        self,
        user_id: str,
        organization_id: Optional[str] = None,
        include_shared: bool = True
    ) -> list[QueryTemplate]:
        """Get templates accessible to a user."""
        ...
    
    def update_template(self, template: QueryTemplate) -> bool:
        """Update an existing template."""
        ...
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template."""
        ...


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class TemplateExecutionResult:
    """
    Result of template execution.
    
    Attributes:
        template_id: ID of the executed template.
        substituted_query: Query after parameter substitution.
        response: Query response or clarification request.
    """
    template_id: str
    substituted_query: str
    response: Union[QueryResponse, ClarificationRequest]


# =============================================================================
# Template Manager
# =============================================================================


class TemplateManager:
    """
    Manages query templates with parameter substitution.
    
    Provides functionality for creating, storing, and executing
    parameterized query templates. Templates use {{parameter_name}}
    syntax for placeholders.
    
    All dependencies are injected via constructor following DIP.
    
    Implements Requirements:
    - 25.1: Create parameterized query templates
    - 25.2: Support {{parameter_name}} syntax
    - 25.3: Execute templates with parameter substitution
    - 25.4: List templates for user
    - 25.5: Support template sharing within organization
    
    Example:
        >>> manager = TemplateManager(
        ...     query_executor=orchestrator,
        ...     template_store=store
        ... )
        >>> template = manager.create_template(
        ...     name="Quarterly Report",
        ...     template_text="What is the total {{metric}} for {{period}}?",
        ...     created_by="user_123"
        ... )
        >>> result = manager.execute_template(
        ...     template_id=template.template_id,
        ...     parameters={"metric": "revenue", "period": "Q1 2024"}
        ... )
    """
    
    def __init__(
        self,
        query_executor: QueryExecutorProtocol,
        template_store: TemplateStoreProtocol
    ) -> None:
        """
        Initialize TemplateManager with injected dependencies.
        
        Args:
            query_executor: Service for executing queries.
            template_store: Service for storing templates.
            
        Raises:
            ValueError: If any required dependency is None.
        """
        if query_executor is None:
            raise ValueError("query_executor is required")
        if template_store is None:
            raise ValueError("template_store is required")
        
        self._query_executor = query_executor
        self._template_store = template_store
        
        logger.info("TemplateManager initialized")
    
    def create_template(
        self,
        name: str,
        template_text: str,
        created_by: str,
        organization_id: Optional[str] = None,
        is_shared: bool = False
    ) -> QueryTemplate:
        """
        Create a new query template.
        
        Validates the template, extracts parameters, and stores it.
        
        Args:
            name: Human-readable template name.
            template_text: Template text with {{parameter}} placeholders.
            created_by: User ID of the creator.
            organization_id: Optional organization ID for sharing.
            is_shared: Whether to share with organization.
            
        Returns:
            Created QueryTemplate with extracted parameters.
            
        Raises:
            TemplateError: If template validation fails.
        """
        # Validate inputs
        self._validate_template_name(name)
        self._validate_template_text(template_text)
        
        if not created_by or not created_by.strip():
            raise TemplateError(
                "created_by cannot be empty",
                details={"created_by": created_by}
            )
        
        # Extract parameters from template text
        parameters = self.extract_parameters(template_text)
        
        # Generate template ID
        template_id = f"tmpl_{uuid.uuid4().hex[:16]}"
        
        # Create template object
        template = QueryTemplate(
            template_id=template_id,
            name=name.strip(),
            template_text=template_text,
            parameters=parameters,
            created_by=created_by,
            created_at=datetime.utcnow(),
            is_shared=is_shared
        )
        
        # Store template
        success = self._template_store.create_template(template)
        if not success:
            raise TemplateError(
                "Failed to store template",
                details={"template_id": template_id, "name": name}
            )
        
        logger.info(
            f"Created template {template_id}: '{name}' with "
            f"{len(parameters)} parameters"
        )
        
        return template
    
    def get_template(self, template_id: str) -> Optional[QueryTemplate]:
        """
        Get a template by ID.
        
        Args:
            template_id: Unique template identifier.
            
        Returns:
            QueryTemplate if found, None otherwise.
        """
        return self._template_store.get_template(template_id)
    
    def get_templates_for_user(
        self,
        user_id: str,
        organization_id: Optional[str] = None,
        include_shared: bool = True
    ) -> list[QueryTemplate]:
        """
        Get all templates accessible to a user.
        
        Returns templates created by the user and optionally shared
        templates from their organization.
        
        Args:
            user_id: User ID to get templates for.
            organization_id: Optional organization ID for shared templates.
            include_shared: Whether to include shared templates.
            
        Returns:
            List of accessible QueryTemplate objects.
        """
        return self._template_store.get_templates_for_user(
            user_id=user_id,
            organization_id=organization_id,
            include_shared=include_shared
        )
    
    def execute_template(
        self,
        template_id: str,
        parameters: dict[str, str],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        file_hints: Optional[list[str]] = None,
        sheet_hints: Optional[list[str]] = None
    ) -> TemplateExecutionResult:
        """
        Execute a template with parameter substitution.
        
        Retrieves the template, substitutes parameters, and executes
        the resulting query.
        
        Args:
            template_id: ID of the template to execute.
            parameters: Dictionary of parameter values.
            user_id: Optional user ID for tracking.
            session_id: Optional session ID for context.
            file_hints: Optional file hints.
            sheet_hints: Optional sheet hints.
            
        Returns:
            TemplateExecutionResult with substituted query and response.
            
        Raises:
            TemplateError: If template not found or parameter substitution fails.
        """
        # Get template
        template = self._template_store.get_template(template_id)
        if template is None:
            raise TemplateError(
                f"Template not found: {template_id}",
                details={"template_id": template_id}
            )
        
        # Substitute parameters
        substituted_query = self.substitute_parameters(
            template_text=template.template_text,
            parameters=parameters,
            required_parameters=template.parameters
        )
        
        logger.info(
            f"Executing template {template_id} with query: "
            f"{substituted_query[:100]}..."
        )
        
        # Execute query
        response = self._query_executor.process_query(
            query=substituted_query,
            user_id=user_id,
            session_id=session_id,
            file_hints=file_hints,
            sheet_hints=sheet_hints
        )
        
        return TemplateExecutionResult(
            template_id=template_id,
            substituted_query=substituted_query,
            response=response
        )
    
    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        template_text: Optional[str] = None,
        is_shared: Optional[bool] = None,
        user_id: Optional[str] = None
    ) -> QueryTemplate:
        """
        Update an existing template.
        
        Args:
            template_id: ID of the template to update.
            name: Optional new name.
            template_text: Optional new template text.
            is_shared: Optional new sharing setting.
            user_id: User ID for authorization check.
            
        Returns:
            Updated QueryTemplate.
            
        Raises:
            TemplateError: If template not found or update fails.
        """
        # Get existing template
        template = self._template_store.get_template(template_id)
        if template is None:
            raise TemplateError(
                f"Template not found: {template_id}",
                details={"template_id": template_id}
            )
        
        # Check authorization (only creator can update)
        if user_id and template.created_by != user_id:
            raise TemplateError(
                "Not authorized to update this template",
                details={
                    "template_id": template_id,
                    "user_id": user_id,
                    "created_by": template.created_by
                }
            )
        
        # Update fields
        if name is not None:
            self._validate_template_name(name)
            template = QueryTemplate(
                template_id=template.template_id,
                name=name.strip(),
                template_text=template.template_text,
                parameters=template.parameters,
                created_by=template.created_by,
                created_at=template.created_at,
                is_shared=template.is_shared
            )
        
        if template_text is not None:
            self._validate_template_text(template_text)
            parameters = self.extract_parameters(template_text)
            template = QueryTemplate(
                template_id=template.template_id,
                name=template.name,
                template_text=template_text,
                parameters=parameters,
                created_by=template.created_by,
                created_at=template.created_at,
                is_shared=template.is_shared
            )
        
        if is_shared is not None:
            template = QueryTemplate(
                template_id=template.template_id,
                name=template.name,
                template_text=template.template_text,
                parameters=template.parameters,
                created_by=template.created_by,
                created_at=template.created_at,
                is_shared=is_shared
            )
        
        # Store updated template
        success = self._template_store.update_template(template)
        if not success:
            raise TemplateError(
                "Failed to update template",
                details={"template_id": template_id}
            )
        
        logger.info(f"Updated template {template_id}")
        return template
    
    def delete_template(
        self,
        template_id: str,
        user_id: Optional[str] = None
    ) -> bool:
        """
        Delete a template.
        
        Args:
            template_id: ID of the template to delete.
            user_id: User ID for authorization check.
            
        Returns:
            True if deleted successfully.
            
        Raises:
            TemplateError: If template not found or not authorized.
        """
        # Get existing template for authorization check
        template = self._template_store.get_template(template_id)
        if template is None:
            raise TemplateError(
                f"Template not found: {template_id}",
                details={"template_id": template_id}
            )
        
        # Check authorization (only creator can delete)
        if user_id and template.created_by != user_id:
            raise TemplateError(
                "Not authorized to delete this template",
                details={
                    "template_id": template_id,
                    "user_id": user_id,
                    "created_by": template.created_by
                }
            )
        
        success = self._template_store.delete_template(template_id)
        if success:
            logger.info(f"Deleted template {template_id}")
        
        return success
    
    @staticmethod
    def extract_parameters(template_text: str) -> list[str]:
        """
        Extract parameter names from template text.
        
        Finds all {{parameter_name}} patterns and returns unique
        parameter names in order of first occurrence.
        
        Args:
            template_text: Template text with {{parameter}} placeholders.
            
        Returns:
            List of unique parameter names.
            
        Example:
            >>> TemplateManager.extract_parameters(
            ...     "Total {{metric}} for {{period}} in {{region}}"
            ... )
            ['metric', 'period', 'region']
        """
        matches = PARAMETER_PATTERN.findall(template_text)
        
        # Preserve order while removing duplicates
        seen = set()
        parameters = []
        for param in matches:
            if param not in seen:
                seen.add(param)
                parameters.append(param)
        
        return parameters
    
    @staticmethod
    def substitute_parameters(
        template_text: str,
        parameters: dict[str, str],
        required_parameters: Optional[list[str]] = None
    ) -> str:
        """
        Substitute parameters in template text.
        
        Replaces all {{parameter_name}} patterns with provided values.
        Validates that all required parameters are provided.
        
        Args:
            template_text: Template text with {{parameter}} placeholders.
            parameters: Dictionary mapping parameter names to values.
            required_parameters: Optional list of required parameter names.
            
        Returns:
            Template text with parameters substituted.
            
        Raises:
            TemplateError: If required parameters are missing.
            
        Example:
            >>> TemplateManager.substitute_parameters(
            ...     "Total {{metric}} for {{period}}",
            ...     {"metric": "revenue", "period": "Q1 2024"}
            ... )
            'Total revenue for Q1 2024'
        """
        # Validate required parameters
        if required_parameters:
            missing = [p for p in required_parameters if p not in parameters]
            if missing:
                raise TemplateError(
                    f"Missing required parameters: {', '.join(missing)}",
                    details={
                        "missing_parameters": missing,
                        "provided_parameters": list(parameters.keys()),
                        "required_parameters": required_parameters
                    }
                )
        
        # Perform substitution
        result = template_text
        for param_name, param_value in parameters.items():
            pattern = f"{{{{{param_name}}}}}"
            result = result.replace(pattern, str(param_value))
        
        # Check for remaining unsubstituted parameters
        remaining = PARAMETER_PATTERN.findall(result)
        if remaining:
            raise TemplateError(
                f"Unsubstituted parameters remain: {', '.join(remaining)}",
                details={
                    "remaining_parameters": remaining,
                    "provided_parameters": list(parameters.keys())
                }
            )
        
        return result
    
    def _validate_template_name(self, name: str) -> None:
        """Validate template name."""
        if not name or not name.strip():
            raise TemplateError(
                "Template name cannot be empty",
                details={"name": name}
            )
        
        if len(name) > MAX_TEMPLATE_NAME_LENGTH:
            raise TemplateError(
                f"Template name exceeds maximum length of {MAX_TEMPLATE_NAME_LENGTH}",
                details={"name_length": len(name), "max_length": MAX_TEMPLATE_NAME_LENGTH}
            )
    
    def _validate_template_text(self, template_text: str) -> None:
        """Validate template text."""
        if not template_text or not template_text.strip():
            raise TemplateError(
                "Template text cannot be empty",
                details={"template_text": template_text}
            )
        
        if len(template_text) > MAX_TEMPLATE_TEXT_LENGTH:
            raise TemplateError(
                f"Template text exceeds maximum length of {MAX_TEMPLATE_TEXT_LENGTH}",
                details={
                    "text_length": len(template_text),
                    "max_length": MAX_TEMPLATE_TEXT_LENGTH
                }
            )
        
        # Validate parameter syntax
        # Check for malformed parameters (e.g., {param} instead of {{param}})
        single_brace_pattern = re.compile(r'(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})')
        malformed = single_brace_pattern.findall(template_text)
        if malformed:
            raise TemplateError(
                f"Malformed parameter syntax. Use {{{{param}}}} not {{param}}. "
                f"Found: {', '.join(malformed)}",
                details={"malformed_parameters": malformed}
            )
