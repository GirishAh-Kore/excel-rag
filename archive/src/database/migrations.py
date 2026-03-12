"""
Database migration utilities for schema updates.

This module provides utilities for managing database schema migrations
and version tracking.
"""

import logging
from datetime import datetime
from typing import Callable, Dict, List

from .connection import DatabaseConnection

logger = logging.getLogger(__name__)


class Migration:
    """Represents a single database migration."""

    def __init__(
        self,
        version: int,
        description: str,
        up: Callable[[DatabaseConnection], None],
        down: Callable[[DatabaseConnection], None]
    ):
        """
        Initialize a migration.

        Args:
            version: Migration version number
            description: Description of the migration
            up: Function to apply the migration
            down: Function to rollback the migration
        """
        self.version = version
        self.description = description
        self.up = up
        self.down = down


class MigrationManager:
    """Manages database migrations."""

    def __init__(self, db: DatabaseConnection):
        """
        Initialize migration manager.

        Args:
            db: Database connection instance
        """
        self.db = db
        self._ensure_migrations_table()

    def _ensure_migrations_table(self) -> None:
        """Create migrations tracking table if not exists."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        with self.db.get_cursor() as cursor:
            cursor.execute(create_table_sql)

    def get_current_version(self) -> int:
        """
        Get the current schema version.

        Returns:
            Current version number (0 if no migrations applied)
        """
        query = "SELECT MAX(version) as version FROM schema_migrations"
        results = self.db.execute_query(query)
        version = results[0]["version"] if results and results[0]["version"] else 0
        return version

    def is_migration_applied(self, version: int) -> bool:
        """
        Check if a migration has been applied.

        Args:
            version: Migration version to check

        Returns:
            True if migration is applied, False otherwise
        """
        query = "SELECT COUNT(*) as count FROM schema_migrations WHERE version = ?"
        results = self.db.execute_query(query, (version,))
        return results[0]["count"] > 0

    def apply_migration(self, migration: Migration) -> None:
        """
        Apply a migration.

        Args:
            migration: Migration to apply

        Raises:
            RuntimeError: If migration is already applied
        """
        if self.is_migration_applied(migration.version):
            raise RuntimeError(
                f"Migration {migration.version} is already applied"
            )

        logger.info(
            f"Applying migration {migration.version}: {migration.description}"
        )

        try:
            # Apply the migration
            migration.up(self.db)

            # Record the migration
            insert_sql = """
            INSERT INTO schema_migrations (version, description)
            VALUES (?, ?)
            """
            self.db.execute_insert(
                insert_sql,
                (migration.version, migration.description)
            )

            logger.info(f"Migration {migration.version} applied successfully")

        except Exception as e:
            logger.error(f"Failed to apply migration {migration.version}: {e}")
            raise

    def rollback_migration(self, migration: Migration) -> None:
        """
        Rollback a migration.

        Args:
            migration: Migration to rollback

        Raises:
            RuntimeError: If migration is not applied
        """
        if not self.is_migration_applied(migration.version):
            raise RuntimeError(
                f"Migration {migration.version} is not applied"
            )

        logger.info(
            f"Rolling back migration {migration.version}: {migration.description}"
        )

        try:
            # Rollback the migration
            migration.down(self.db)

            # Remove the migration record
            delete_sql = "DELETE FROM schema_migrations WHERE version = ?"
            self.db.execute_update(delete_sql, (migration.version,))

            logger.info(f"Migration {migration.version} rolled back successfully")

        except Exception as e:
            logger.error(f"Failed to rollback migration {migration.version}: {e}")
            raise

    def apply_all_migrations(self, migrations: List[Migration]) -> None:
        """
        Apply all pending migrations.

        Args:
            migrations: List of migrations to apply
        """
        current_version = self.get_current_version()
        pending_migrations = [
            m for m in migrations if m.version > current_version
        ]

        if not pending_migrations:
            logger.info("No pending migrations")
            return

        logger.info(f"Applying {len(pending_migrations)} pending migrations")

        for migration in sorted(pending_migrations, key=lambda m: m.version):
            self.apply_migration(migration)

        logger.info("All migrations applied successfully")

    def get_migration_history(self) -> List[Dict]:
        """
        Get the history of applied migrations.

        Returns:
            List of migration records
        """
        query = """
        SELECT version, description, applied_at
        FROM schema_migrations
        ORDER BY version
        """
        results = self.db.execute_query(query)
        return [dict(row) for row in results]


# Example migrations (can be extended as needed)
def _add_example_column_up(db: DatabaseConnection) -> None:
    """Example migration: Add a new column."""
    # This is just an example - no actual migration needed for initial schema
    pass


def _add_example_column_down(db: DatabaseConnection) -> None:
    """Example migration rollback: Remove the column."""
    # This is just an example - no actual migration needed for initial schema
    pass


# Registry of all migrations
MIGRATIONS: List[Migration] = [
    # Migration(
    #     version=1,
    #     description="Initial schema",
    #     up=_add_example_column_up,
    #     down=_add_example_column_down
    # ),
    # Add more migrations here as needed
]
