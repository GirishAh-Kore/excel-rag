"""
Database schema definitions for the Google Drive Excel RAG system.

This module defines the SQLite database schema including tables for files,
sheets, pivot tables, charts, user preferences, and query history.
"""

# SQL statements for creating tables
CREATE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_time TIMESTAMP NOT NULL,
    md5_checksum TEXT NOT NULL,
    indexed_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_SHEETS_TABLE = """
CREATE TABLE IF NOT EXISTS sheets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    column_count INTEGER NOT NULL DEFAULT 0,
    headers TEXT,
    data_types TEXT,
    has_dates BOOLEAN DEFAULT 0,
    has_numbers BOOLEAN DEFAULT 0,
    has_pivot_tables BOOLEAN DEFAULT 0,
    has_charts BOOLEAN DEFAULT 0,
    pivot_count INTEGER DEFAULT 0,
    chart_count INTEGER DEFAULT 0,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(file_id) ON DELETE CASCADE,
    UNIQUE(file_id, sheet_name)
);
"""

CREATE_PIVOT_TABLES_TABLE = """
CREATE TABLE IF NOT EXISTS pivot_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    source_range TEXT,
    row_fields TEXT,
    column_fields TEXT,
    data_fields TEXT,
    filters TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id) ON DELETE CASCADE
);
"""

CREATE_CHARTS_TABLE = """
CREATE TABLE IF NOT EXISTS charts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    chart_type TEXT NOT NULL,
    title TEXT,
    source_range TEXT,
    series TEXT,
    x_axis_label TEXT,
    y_axis_label TEXT,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sheet_id) REFERENCES sheets(id) ON DELETE CASCADE
);
"""

CREATE_USER_PREFERENCES_TABLE = """
CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_pattern TEXT NOT NULL,
    selected_file_id TEXT NOT NULL,
    selected_sheet_name TEXT,
    confidence_score REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (selected_file_id) REFERENCES files(file_id) ON DELETE CASCADE
);
"""

CREATE_QUERY_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    query TEXT NOT NULL,
    selected_files TEXT,
    answer TEXT,
    confidence REAL,
    processing_time_ms INTEGER,
    is_comparison BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Index definitions for frequently queried columns
CREATE_FILES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);",
    "CREATE INDEX IF NOT EXISTS idx_files_modified_time ON files(modified_time);",
    "CREATE INDEX IF NOT EXISTS idx_files_md5_checksum ON files(md5_checksum);",
    "CREATE INDEX IF NOT EXISTS idx_files_name ON files(name);",
]

CREATE_SHEETS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sheets_file_id ON sheets(file_id);",
    "CREATE INDEX IF NOT EXISTS idx_sheets_has_pivot_tables ON sheets(has_pivot_tables);",
    "CREATE INDEX IF NOT EXISTS idx_sheets_has_charts ON sheets(has_charts);",
]

CREATE_PIVOT_TABLES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pivot_tables_sheet_id ON pivot_tables(sheet_id);",
]

CREATE_CHARTS_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_charts_sheet_id ON charts(sheet_id);",
]

CREATE_USER_PREFERENCES_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_user_preferences_file_id ON user_preferences(selected_file_id);",
    "CREATE INDEX IF NOT EXISTS idx_user_preferences_created_at ON user_preferences(created_at);",
]

CREATE_QUERY_HISTORY_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_query_history_session_id ON query_history(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_query_history_created_at ON query_history(created_at);",
]

# Trigger to update updated_at timestamp
CREATE_FILES_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS update_files_timestamp 
AFTER UPDATE ON files
FOR EACH ROW
BEGIN
    UPDATE files SET updated_at = CURRENT_TIMESTAMP WHERE file_id = NEW.file_id;
END;
"""

CREATE_SHEETS_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS update_sheets_timestamp 
AFTER UPDATE ON sheets
FOR EACH ROW
BEGIN
    UPDATE sheets SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
"""

CREATE_PIVOT_TABLES_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS update_pivot_tables_timestamp 
AFTER UPDATE ON pivot_tables
FOR EACH ROW
BEGIN
    UPDATE pivot_tables SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
"""

CREATE_CHARTS_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS update_charts_timestamp 
AFTER UPDATE ON charts
FOR EACH ROW
BEGIN
    UPDATE charts SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
END;
"""

# All table creation statements in order
ALL_TABLES = [
    CREATE_FILES_TABLE,
    CREATE_SHEETS_TABLE,
    CREATE_PIVOT_TABLES_TABLE,
    CREATE_CHARTS_TABLE,
    CREATE_USER_PREFERENCES_TABLE,
    CREATE_QUERY_HISTORY_TABLE,
]

# All index creation statements
ALL_INDEXES = (
    CREATE_FILES_INDEXES +
    CREATE_SHEETS_INDEXES +
    CREATE_PIVOT_TABLES_INDEXES +
    CREATE_CHARTS_INDEXES +
    CREATE_USER_PREFERENCES_INDEXES +
    CREATE_QUERY_HISTORY_INDEXES
)

# All trigger creation statements
ALL_TRIGGERS = [
    CREATE_FILES_UPDATE_TRIGGER,
    CREATE_SHEETS_UPDATE_TRIGGER,
    CREATE_PIVOT_TABLES_UPDATE_TRIGGER,
    CREATE_CHARTS_UPDATE_TRIGGER,
]
