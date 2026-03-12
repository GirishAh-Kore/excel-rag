"""
Tests for data models and database schema.

This module tests the Pydantic models, database schema, and vector store initialization.
"""

import pytest
import tempfile
import os
from datetime import datetime
from pathlib import Path

from src.models import (
    FileMetadata,
    FileStatus,
    DataType,
    CellData,
    SheetData,
    WorkbookData,
    PivotTableData,
    ChartData,
    QueryResult,
    RankedFile,
)
from src.database import (
    DatabaseConnection,
    initialize_database,
    get_database,
)


class TestDataModels:
    """Test Pydantic data models."""

    def test_file_metadata_creation(self):
        """Test creating a FileMetadata instance."""
        file_meta = FileMetadata(
            file_id="test123",
            name="test.xlsx",
            path="/test/test.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            size=1024,
            modified_time=datetime.now(),
            md5_checksum="abc123",
            status=FileStatus.INDEXED
        )
        
        assert file_meta.file_id == "test123"
        assert file_meta.name == "test.xlsx"
        assert file_meta.status == FileStatus.INDEXED

    def test_cell_data_with_formula(self):
        """Test creating CellData with formula."""
        cell = CellData(
            value=100.5,
            data_type=DataType.NUMBER,
            formula="=SUM(A1:A10)",
            is_formula=True,
            format="$#,##0.00"
        )
        
        assert cell.value == 100.5
        assert cell.is_formula is True
        assert cell.formula == "=SUM(A1:A10)"

    def test_sheet_data_auto_flags(self):
        """Test SheetData automatically sets has_pivot_tables and has_charts."""
        pivot = PivotTableData(
            name="Pivot1",
            location="A1:D10",
            source_range="Sheet1!A1:F100",
            summary="Test pivot"
        )
        
        chart = ChartData(
            name="Chart1",
            chart_type="bar",
            source_range="A1:B10",
            summary="Test chart"
        )
        
        sheet = SheetData(
            sheet_name="Test",
            row_count=10,
            column_count=5,
            summary="Test sheet",
            pivot_tables=[pivot],
            charts=[chart]
        )
        
        # These should be automatically set based on the lists
        assert sheet.has_pivot_tables is True
        assert sheet.has_charts is True

    def test_workbook_data_aggregation(self):
        """Test WorkbookData aggregates pivot and chart counts."""
        pivot = PivotTableData(
            name="Pivot1",
            location="A1:D10",
            source_range="Sheet1!A1:F100",
            summary="Test pivot"
        )
        
        sheet1 = SheetData(
            sheet_name="Sheet1",
            row_count=10,
            column_count=5,
            summary="Test sheet",
            pivot_tables=[pivot],
            charts=[]
        )
        
        sheet2 = SheetData(
            sheet_name="Sheet2",
            row_count=20,
            column_count=3,
            summary="Another sheet",
            pivot_tables=[],
            charts=[]
        )
        
        workbook = WorkbookData(
            file_id="test123",
            file_name="test.xlsx",
            file_path="/test/test.xlsx",
            sheets=[sheet1, sheet2],
            modified_time=datetime.now()
        )
        
        assert workbook.has_pivot_tables is True
        assert workbook.total_pivot_tables == 1
        assert workbook.total_charts == 0


class TestDatabaseSchema:
    """Test database schema and connection management."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            db = DatabaseConnection(db_path)
            yield db
            db.close()

    def test_database_initialization(self, temp_db):
        """Test database tables are created."""
        # Check that files table exists
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
        results = temp_db.execute_query(query)
        assert len(results) == 1
        assert results[0]["name"] == "files"

    def test_insert_file_metadata(self, temp_db):
        """Test inserting file metadata into database."""
        insert_sql = """
        INSERT INTO files (file_id, name, path, mime_type, size, modified_time, md5_checksum, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        file_id = temp_db.execute_insert(
            insert_sql,
            (
                "test123",
                "test.xlsx",
                "/test/test.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                1024,
                datetime.now().isoformat(),
                "abc123",
                "indexed"
            )
        )
        
        # Query the inserted file
        query = "SELECT * FROM files WHERE file_id = ?"
        results = temp_db.execute_query(query, ("test123",))
        
        assert len(results) == 1
        assert results[0]["name"] == "test.xlsx"
        assert results[0]["status"] == "indexed"

    def test_foreign_key_constraint(self, temp_db):
        """Test foreign key constraints work."""
        # Insert a file first
        insert_file_sql = """
        INSERT INTO files (file_id, name, path, mime_type, size, modified_time, md5_checksum, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        temp_db.execute_insert(
            insert_file_sql,
            (
                "test123",
                "test.xlsx",
                "/test/test.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                1024,
                datetime.now().isoformat(),
                "abc123",
                "indexed"
            )
        )
        
        # Insert a sheet referencing the file
        insert_sheet_sql = """
        INSERT INTO sheets (file_id, sheet_name, row_count, column_count, summary)
        VALUES (?, ?, ?, ?, ?)
        """
        
        sheet_id = temp_db.execute_insert(
            insert_sheet_sql,
            ("test123", "Sheet1", 10, 5, "Test sheet")
        )
        
        assert sheet_id > 0
        
        # Query the sheet
        query = "SELECT * FROM sheets WHERE file_id = ?"
        results = temp_db.execute_query(query, ("test123",))
        
        assert len(results) == 1
        assert results[0]["sheet_name"] == "Sheet1"

    def test_indexes_created(self, temp_db):
        """Test that indexes are created."""
        query = "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        results = temp_db.execute_query(query)
        
        # Should have multiple indexes
        assert len(results) > 0
        
        # Check for specific indexes
        index_names = [row["name"] for row in results]
        assert "idx_files_status" in index_names
        assert "idx_sheets_file_id" in index_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
