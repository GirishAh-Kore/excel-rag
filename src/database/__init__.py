"""Database management and operations"""

from .connection import DatabaseConnection, get_database, initialize_database
from .migrations import Migration, MigrationManager, MIGRATIONS
from .schema import (
    ALL_INDEXES,
    ALL_TABLES,
    ALL_TRIGGERS,
    CREATE_CHARTS_TABLE,
    CREATE_FILES_TABLE,
    CREATE_PIVOT_TABLES_TABLE,
    CREATE_QUERY_HISTORY_TABLE,
    CREATE_SHEETS_TABLE,
    CREATE_USER_PREFERENCES_TABLE,
)

__all__ = [
    "DatabaseConnection",
    "get_database",
    "initialize_database",
    "Migration",
    "MigrationManager",
    "MIGRATIONS",
    "ALL_INDEXES",
    "ALL_TABLES",
    "ALL_TRIGGERS",
    "CREATE_CHARTS_TABLE",
    "CREATE_FILES_TABLE",
    "CREATE_PIVOT_TABLES_TABLE",
    "CREATE_QUERY_HISTORY_TABLE",
    "CREATE_SHEETS_TABLE",
    "CREATE_USER_PREFERENCES_TABLE",
]
