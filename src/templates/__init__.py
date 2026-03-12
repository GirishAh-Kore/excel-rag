"""
Query template management module.

This module provides template management capabilities for creating,
storing, and executing parameterized query templates.

Key Components:
- TemplateManager: Manages query templates with parameter substitution
- TemplateStore: Persists templates to database

Supports Requirements 25.1, 25.2, 25.3, 25.4, 25.5.
"""

from src.templates.manager import TemplateManager
from src.templates.store import TemplateStore

__all__ = ["TemplateManager", "TemplateStore"]
