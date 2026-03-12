"""
Example usage of data models and database schema.

This script demonstrates how to use the Pydantic models, database connection,
and vector store initialization.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    FileMetadata,
    FileStatus,
    DataType,
    CellData,
    SheetData,
    WorkbookData,
    PivotTableData,
    ChartData,
)
from src.database import initialize_database, get_database
from src.config import AppConfig
from src.abstractions import VectorStoreFactory, EmbeddingServiceFactory
from src.indexing import initialize_vector_store_collections


def example_data_models():
    """Demonstrate creating and using data models."""
    print("=" * 60)
    print("Example 1: Creating Data Models")
    print("=" * 60)
    
    # Create a file metadata instance
    file_meta = FileMetadata(
        file_id="1abc123def456",
        name="Expenses_Jan2024.xlsx",
        path="/Finance/2024/Expenses_Jan2024.xlsx",
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        size=52480,
        modified_time=datetime.now(),
        md5_checksum="5d41402abc4b2a76b9719d911017c592",
        status=FileStatus.INDEXED
    )
    
    print(f"\nFile Metadata:")
    print(f"  Name: {file_meta.name}")
    print(f"  Path: {file_meta.path}")
    print(f"  Status: {file_meta.status.value}")
    print(f"  Size: {file_meta.size} bytes")
    
    # Create a cell with formula
    cell = CellData(
        value=1500.50,
        data_type=DataType.NUMBER,
        formula="=SUM(B2:B9)",
        is_formula=True,
        format="$#,##0.00"
    )
    
    print(f"\nCell Data:")
    print(f"  Value: {cell.value}")
    print(f"  Formula: {cell.formula}")
    print(f"  Format: {cell.format}")
    
    # Create a pivot table
    pivot = PivotTableData(
        name="SalesByRegion",
        location="A1:D10",
        source_range="Sheet1!A1:F100",
        row_fields=["Region", "Product"],
        column_fields=["Month"],
        data_fields=["Sum of Sales"],
        summary="Pivot table showing Sum of Sales grouped by Region and Product across months"
    )
    
    print(f"\nPivot Table:")
    print(f"  Name: {pivot.name}")
    print(f"  Row Fields: {', '.join(pivot.row_fields)}")
    print(f"  Summary: {pivot.summary}")
    
    # Create a sheet with pivot table
    sheet = SheetData(
        sheet_name="Summary",
        headers=["Month", "Revenue", "Expenses", "Profit"],
        row_count=12,
        column_count=4,
        summary="Monthly financial summary",
        has_numbers=True,
        pivot_tables=[pivot]
    )
    
    print(f"\nSheet Data:")
    print(f"  Name: {sheet.sheet_name}")
    print(f"  Rows: {sheet.row_count}, Columns: {sheet.column_count}")
    print(f"  Has Pivot Tables: {sheet.has_pivot_tables}")
    print(f"  Number of Pivot Tables: {len(sheet.pivot_tables)}")
    
    # Create a workbook
    workbook = WorkbookData(
        file_id=file_meta.file_id,
        file_name=file_meta.name,
        file_path=file_meta.path,
        sheets=[sheet],
        modified_time=file_meta.modified_time
    )
    
    print(f"\nWorkbook Data:")
    print(f"  File: {workbook.file_name}")
    print(f"  Sheets: {len(workbook.sheets)}")
    print(f"  Has Pivot Tables: {workbook.has_pivot_tables}")
    print(f"  Total Pivot Tables: {workbook.total_pivot_tables}")


def example_database():
    """Demonstrate database operations."""
    print("\n" + "=" * 60)
    print("Example 2: Database Operations")
    print("=" * 60)
    
    # Initialize database
    db_path = "/tmp/test_rag.db"
    db = initialize_database(db_path)
    
    print(f"\nDatabase initialized at: {db_path}")
    
    # Insert a file
    insert_sql = """
    INSERT INTO files (file_id, name, path, mime_type, size, modified_time, md5_checksum, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    file_id = db.execute_insert(
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
    
    print(f"\nInserted file with ID: test123")
    
    # Query the file
    query = "SELECT * FROM files WHERE file_id = ?"
    results = db.execute_query(query, ("test123",))
    
    if results:
        file_row = results[0]
        print(f"\nQueried file:")
        print(f"  Name: {file_row['name']}")
        print(f"  Status: {file_row['status']}")
        print(f"  Size: {file_row['size']} bytes")
    
    # Insert a sheet
    insert_sheet_sql = """
    INSERT INTO sheets (file_id, sheet_name, row_count, column_count, summary)
    VALUES (?, ?, ?, ?, ?)
    """
    
    sheet_id = db.execute_insert(
        insert_sheet_sql,
        ("test123", "Sheet1", 10, 5, "Test sheet")
    )
    
    print(f"\nInserted sheet with ID: {sheet_id}")
    
    # Query sheets for the file
    query_sheets = "SELECT * FROM sheets WHERE file_id = ?"
    sheet_results = db.execute_query(query_sheets, ("test123",))
    
    print(f"\nSheets for file test123:")
    for sheet_row in sheet_results:
        print(f"  - {sheet_row['sheet_name']} ({sheet_row['row_count']} rows)")
    
    db.close()
    print(f"\nDatabase connection closed")


def example_vector_store():
    """Demonstrate vector store initialization."""
    print("\n" + "=" * 60)
    print("Example 3: Vector Store Initialization")
    print("=" * 60)
    
    # Note: This requires actual configuration and services
    # This is a demonstration of the API, not a working example
    
    print("\nTo initialize vector store collections:")
    print("1. Create AppConfig from environment variables")
    print("2. Create VectorStore using VectorStoreFactory")
    print("3. Create EmbeddingService using EmbeddingServiceFactory")
    print("4. Call initialize_vector_store_collections()")
    
    print("\nExample code:")
    print("""
    from src.config import AppConfig
    from src.abstractions import VectorStoreFactory, EmbeddingServiceFactory
    from src.indexing import initialize_vector_store_collections
    
    # Load configuration
    config = AppConfig.from_env()
    
    # Create services
    vector_store = VectorStoreFactory.create(
        config.vector_store.provider,
        config.vector_store.config
    )
    
    embedding_service = EmbeddingServiceFactory.create(
        config.embedding.provider,
        config.embedding.config
    )
    
    # Initialize collections
    success = initialize_vector_store_collections(
        vector_store,
        embedding_service,
        recreate=False
    )
    
    if success:
        print("All collections initialized successfully!")
    """)


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Data Models and Database Schema Examples")
    print("=" * 60)
    
    example_data_models()
    example_database()
    example_vector_store()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
