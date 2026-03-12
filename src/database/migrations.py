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


# Migration 1: Add chunk visibility and traceability tables
def _add_chunk_visibility_tables_up(db: DatabaseConnection) -> None:
    """
    Add tables for chunk visibility and query traceability.

    Creates the following tables:
    - chunk_versions: Track re-indexing changes with version history
    - query_traces: Audit trail for query processing
    - data_lineage: Track data flow from source to answer
    - extraction_metadata: Store extraction process details
    - chunk_feedback: Collect user feedback on chunk quality

    Requirements: 16.2, 16.5, 17.1, 21.1, 27.1
    """
    # Chunk versions for tracking re-indexing changes
    create_chunk_versions = """
    CREATE TABLE IF NOT EXISTS chunk_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chunk_id TEXT NOT NULL,
        file_id TEXT NOT NULL,
        version_number INTEGER NOT NULL,
        chunk_text TEXT NOT NULL,
        raw_source_data TEXT,
        start_row INTEGER,
        end_row INTEGER,
        extraction_strategy TEXT NOT NULL,
        indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        change_summary TEXT,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
        UNIQUE(chunk_id, version_number)
    );
    """

    # Query traces for audit
    create_query_traces = """
    CREATE TABLE IF NOT EXISTS query_traces (
        trace_id TEXT PRIMARY KEY,
        query_text TEXT NOT NULL,
        user_id TEXT,
        session_id TEXT,
        file_selection_json TEXT,
        sheet_selection_json TEXT,
        query_type TEXT,
        classification_confidence REAL,
        chunks_retrieved TEXT,
        answer_text TEXT,
        citations_json TEXT,
        answer_confidence REAL,
        total_processing_time_ms INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP
    );
    """

    # Data lineage records
    create_data_lineage = """
    CREATE TABLE IF NOT EXISTS data_lineage (
        lineage_id TEXT PRIMARY KEY,
        trace_id TEXT NOT NULL,
        answer_component TEXT NOT NULL,
        file_id TEXT NOT NULL,
        sheet_name TEXT NOT NULL,
        cell_range TEXT NOT NULL,
        source_value TEXT,
        chunk_id TEXT NOT NULL,
        embedding_id TEXT,
        retrieval_score REAL,
        indexed_at TIMESTAMP,
        last_verified_at TIMESTAMP,
        is_stale BOOLEAN DEFAULT 0,
        stale_reason TEXT,
        FOREIGN KEY (trace_id) REFERENCES query_traces(trace_id) ON DELETE CASCADE,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE
    );
    """

    # Extraction metadata
    create_extraction_metadata = """
    CREATE TABLE IF NOT EXISTS extraction_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT NOT NULL UNIQUE,
        strategy_used TEXT NOT NULL,
        strategy_selected_reason TEXT,
        complexity_score REAL,
        quality_score REAL NOT NULL,
        has_headers BOOLEAN,
        has_data BOOLEAN,
        data_completeness REAL,
        structure_clarity REAL,
        extraction_errors TEXT,
        extraction_warnings TEXT,
        fallback_used BOOLEAN DEFAULT 0,
        fallback_reason TEXT,
        extraction_duration_ms INTEGER,
        extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE
    );
    """

    # Chunk feedback
    create_chunk_feedback = """
    CREATE TABLE IF NOT EXISTS chunk_feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chunk_id TEXT NOT NULL,
        feedback_type TEXT NOT NULL,
        rating INTEGER CHECK(rating >= 1 AND rating <= 5),
        comment TEXT,
        user_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    with db.get_cursor() as cursor:
        cursor.execute(create_chunk_versions)
        cursor.execute(create_query_traces)
        cursor.execute(create_data_lineage)
        cursor.execute(create_extraction_metadata)
        cursor.execute(create_chunk_feedback)

    logger.info("Created chunk visibility and traceability tables")


def _add_chunk_visibility_tables_down(db: DatabaseConnection) -> None:
    """
    Remove chunk visibility and traceability tables.

    Drops tables in reverse dependency order.
    """
    drop_statements = [
        "DROP TABLE IF EXISTS chunk_feedback;",
        "DROP TABLE IF EXISTS extraction_metadata;",
        "DROP TABLE IF EXISTS data_lineage;",
        "DROP TABLE IF EXISTS query_traces;",
        "DROP TABLE IF EXISTS chunk_versions;",
    ]

    with db.get_cursor() as cursor:
        for statement in drop_statements:
            cursor.execute(statement)

    logger.info("Dropped chunk visibility and traceability tables")


# Migration 2: Add enterprise tables
def _add_enterprise_tables_up(db: DatabaseConnection) -> None:
    """
    Add enterprise tables for templates, webhooks, access control, and caching.

    Creates the following tables:
    - query_templates: Parameterized query templates for reuse
    - webhooks: Webhook registration for event notifications
    - webhook_deliveries: Track webhook delivery attempts
    - file_access_control: Role-based access control for files
    - access_audit_log: Audit log for access attempts
    - named_ranges: Excel named ranges
    - excel_tables: Excel tables (ListObjects)
    - query_cache: Cache for query results

    Requirements: 25.1, 28.1, 29.1, 32.1, 43.1
    """
    # Query templates
    create_query_templates = """
    CREATE TABLE IF NOT EXISTS query_templates (
        template_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        template_text TEXT NOT NULL,
        parameters TEXT NOT NULL,
        created_by TEXT NOT NULL,
        organization_id TEXT,
        is_shared BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    # Webhooks
    create_webhooks = """
    CREATE TABLE IF NOT EXISTS webhooks (
        webhook_id TEXT PRIMARY KEY,
        url TEXT NOT NULL,
        events TEXT NOT NULL,
        secret TEXT,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    """

    # Webhook deliveries
    create_webhook_deliveries = """
    CREATE TABLE IF NOT EXISTS webhook_deliveries (
        delivery_id TEXT PRIMARY KEY,
        webhook_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL,
        attempts INTEGER DEFAULT 0,
        last_attempt_at TIMESTAMP,
        response_code INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (webhook_id) REFERENCES webhooks(webhook_id) ON DELETE CASCADE
    );
    """

    # File access control
    create_file_access_control = """
    CREATE TABLE IF NOT EXISTS file_access_control (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        role TEXT NOT NULL,
        granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        granted_by TEXT NOT NULL,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
        UNIQUE(file_id, user_id)
    );
    """

    # Access audit log
    create_access_audit_log = """
    CREATE TABLE IF NOT EXISTS access_audit_log (
        log_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT NOT NULL,
        action TEXT NOT NULL,
        access_granted BOOLEAN NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT
    );
    """

    # Named ranges
    create_named_ranges = """
    CREATE TABLE IF NOT EXISTS named_ranges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT NOT NULL,
        name TEXT NOT NULL,
        cell_range TEXT NOT NULL,
        sheet_name TEXT,
        scope TEXT NOT NULL,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE
    );
    """

    # Excel tables
    create_excel_tables = """
    CREATE TABLE IF NOT EXISTS excel_tables (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT NOT NULL,
        name TEXT NOT NULL,
        cell_range TEXT NOT NULL,
        sheet_name TEXT NOT NULL,
        headers TEXT NOT NULL,
        row_count INTEGER NOT NULL,
        FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE
    );
    """

    # Query cache
    create_query_cache = """
    CREATE TABLE IF NOT EXISTS query_cache (
        cache_key TEXT PRIMARY KEY,
        query_text TEXT NOT NULL,
        file_ids TEXT NOT NULL,
        result TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL
    );
    """

    # Create indexes for enterprise tables
    create_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id);",
        "CREATE INDEX IF NOT EXISTS idx_file_access_control_file_id ON file_access_control(file_id);",
        "CREATE INDEX IF NOT EXISTS idx_file_access_control_user_id ON file_access_control(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_access_audit_log_user_id ON access_audit_log(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_access_audit_log_timestamp ON access_audit_log(timestamp);",
        "CREATE INDEX IF NOT EXISTS idx_named_ranges_file_id ON named_ranges(file_id);",
        "CREATE INDEX IF NOT EXISTS idx_excel_tables_file_id ON excel_tables(file_id);",
        "CREATE INDEX IF NOT EXISTS idx_query_cache_expires_at ON query_cache(expires_at);",
    ]

    with db.get_cursor() as cursor:
        cursor.execute(create_query_templates)
        cursor.execute(create_webhooks)
        cursor.execute(create_webhook_deliveries)
        cursor.execute(create_file_access_control)
        cursor.execute(create_access_audit_log)
        cursor.execute(create_named_ranges)
        cursor.execute(create_excel_tables)
        cursor.execute(create_query_cache)
        for index_sql in create_indexes:
            cursor.execute(index_sql)

    logger.info("Created enterprise tables")


def _add_enterprise_tables_down(db: DatabaseConnection) -> None:
    """
    Remove enterprise tables.

    Drops tables in reverse dependency order.
    """
    drop_statements = [
        "DROP TABLE IF EXISTS query_cache;",
        "DROP TABLE IF EXISTS excel_tables;",
        "DROP TABLE IF EXISTS named_ranges;",
        "DROP TABLE IF EXISTS access_audit_log;",
        "DROP TABLE IF EXISTS file_access_control;",
        "DROP TABLE IF EXISTS webhook_deliveries;",
        "DROP TABLE IF EXISTS webhooks;",
        "DROP TABLE IF EXISTS query_templates;",
    ]

    with db.get_cursor() as cursor:
        for statement in drop_statements:
            cursor.execute(statement)

    logger.info("Dropped enterprise tables")


# Migration 3: Add performance indexes for chunk visibility tables
def _add_chunk_visibility_indexes_up(db: DatabaseConnection) -> None:
    """
    Add performance indexes for chunk visibility and traceability tables.

    Creates indexes to support:
    - File selection results within 500ms for up to 1000 indexed files (Req 15.1)
    - Chunk listings within 500ms for files with up to 1000 chunks (Req 15.5)

    Requirements: 15.1, 15.5
    """
    create_indexes = [
        # Chunk versions indexes
        "CREATE INDEX IF NOT EXISTS idx_chunk_versions_file_id ON chunk_versions(file_id);",
        "CREATE INDEX IF NOT EXISTS idx_chunk_versions_chunk_id ON chunk_versions(chunk_id);",
        "CREATE INDEX IF NOT EXISTS idx_chunk_versions_file_chunk ON chunk_versions(file_id, chunk_id);",

        # Query traces indexes
        "CREATE INDEX IF NOT EXISTS idx_query_traces_user_id ON query_traces(user_id);",
        "CREATE INDEX IF NOT EXISTS idx_query_traces_session_id ON query_traces(session_id);",
        "CREATE INDEX IF NOT EXISTS idx_query_traces_created_at ON query_traces(created_at);",
        "CREATE INDEX IF NOT EXISTS idx_query_traces_user_session ON query_traces(user_id, session_id);",

        # Data lineage indexes
        "CREATE INDEX IF NOT EXISTS idx_data_lineage_trace_id ON data_lineage(trace_id);",
        "CREATE INDEX IF NOT EXISTS idx_data_lineage_file_id ON data_lineage(file_id);",
        "CREATE INDEX IF NOT EXISTS idx_data_lineage_trace_file ON data_lineage(trace_id, file_id);",

        # Chunk feedback indexes
        "CREATE INDEX IF NOT EXISTS idx_chunk_feedback_chunk_id ON chunk_feedback(chunk_id);",
    ]

    with db.get_cursor() as cursor:
        for index_sql in create_indexes:
            cursor.execute(index_sql)

    logger.info("Created performance indexes for chunk visibility tables")


def _add_chunk_visibility_indexes_down(db: DatabaseConnection) -> None:
    """
    Remove performance indexes for chunk visibility and traceability tables.

    Drops all indexes created in the up migration.
    """
    drop_indexes = [
        # Chunk versions indexes
        "DROP INDEX IF EXISTS idx_chunk_versions_file_id;",
        "DROP INDEX IF EXISTS idx_chunk_versions_chunk_id;",
        "DROP INDEX IF EXISTS idx_chunk_versions_file_chunk;",

        # Query traces indexes
        "DROP INDEX IF EXISTS idx_query_traces_user_id;",
        "DROP INDEX IF EXISTS idx_query_traces_session_id;",
        "DROP INDEX IF EXISTS idx_query_traces_created_at;",
        "DROP INDEX IF EXISTS idx_query_traces_user_session;",

        # Data lineage indexes
        "DROP INDEX IF EXISTS idx_data_lineage_trace_id;",
        "DROP INDEX IF EXISTS idx_data_lineage_file_id;",
        "DROP INDEX IF EXISTS idx_data_lineage_trace_file;",

        # Chunk feedback indexes
        "DROP INDEX IF EXISTS idx_chunk_feedback_chunk_id;",
    ]

    with db.get_cursor() as cursor:
        for drop_sql in drop_indexes:
            cursor.execute(drop_sql)

    logger.info("Dropped performance indexes for chunk visibility tables")


# Registry of all migrations
MIGRATIONS: List[Migration] = [
    Migration(
        version=1,
        description="Add chunk visibility and traceability tables",
        up=_add_chunk_visibility_tables_up,
        down=_add_chunk_visibility_tables_down
    ),
    Migration(
        version=2,
        description="Add enterprise tables",
        up=_add_enterprise_tables_up,
        down=_add_enterprise_tables_down
    ),
    Migration(
        version=3,
        description="Add performance indexes for chunk visibility tables",
        up=_add_chunk_visibility_indexes_up,
        down=_add_chunk_visibility_indexes_down
    ),
]
