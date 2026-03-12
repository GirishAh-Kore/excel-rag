"""
Example usage of the Comparison Engine for comparing data across multiple Excel files.

This script demonstrates how to use the ComparisonEngine to compare data from
multiple files, align sheets, calculate differences, and format results.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.query.comparison_engine import ComparisonEngine
from src.query.sheet_aligner import SheetAligner
from src.query.difference_calculator import DifferenceCalculator
from src.query.comparison_formatter import ComparisonFormatter
from src.gdrive.connector import GoogleDriveConnector
from src.extraction.content_extractor import ContentExtractor
from src.auth.authentication_service import AuthenticationService
from src.abstractions.llm_service_factory import LLMServiceFactory
from src.abstractions.cache_service_factory import CacheServiceFactory
from src.config import AppConfig


def example_basic_comparison():
    """Example: Basic file comparison."""
    print("\n=== Example 1: Basic File Comparison ===\n")
    
    # Initialize services
    config = AppConfig.from_env()
    auth_service = AuthenticationService()
    gdrive_connector = auth_service.get_authenticated_client()
    content_extractor = ContentExtractor()
    
    # Initialize comparison engine
    comparison_engine = ComparisonEngine(
        gdrive_connector=gdrive_connector,
        content_extractor=content_extractor
    )
    
    # Compare two files
    file_ids = [
        "file_id_jan_2024",  # Replace with actual file IDs
        "file_id_feb_2024"
    ]
    
    query = "Compare expenses between January and February 2024"
    
    try:
        result = comparison_engine.compare_files(
            file_ids=file_ids,
            query=query
        )
        
        print(f"Files compared: {result.files_compared}")
        print(f"\nSummary: {result.summary}")
        print(f"\nCommon columns: {result.aligned_data.get('common_columns', [])}")
        
        # Display key differences
        if result.differences:
            print("\nKey Differences:")
            trends = result.differences.get("trends", {})
            for column, trend in trends.items():
                print(f"  - {column}: {trend}")
        
    except Exception as e:
        print(f"Error during comparison: {str(e)}")


def example_sheet_alignment():
    """Example: Sheet alignment with fuzzy matching."""
    print("\n=== Example 2: Sheet Alignment ===\n")
    
    from src.models.domain_models import SheetData
    
    # Create sample sheets
    sheet1 = SheetData(
        sheet_name="Summary",
        headers=["Month", "Revenue", "Expenses", "Profit"],
        rows=[
            {"Month": "Jan", "Revenue": 10000, "Expenses": 7000, "Profit": 3000},
            {"Month": "Feb", "Revenue": 12000, "Expenses": 8000, "Profit": 4000}
        ],
        data_types={"Month": "text", "Revenue": "number", "Expenses": "number", "Profit": "number"},
        row_count=2,
        column_count=4,
        summary="Monthly financial summary",
        has_dates=False,
        has_numbers=True
    )
    
    sheet2 = SheetData(
        sheet_name="Summary",  # Same name
        headers=["Month", "Revenue", "Expenses"],  # Missing "Profit" column
        rows=[
            {"Month": "Jan", "Revenue": 11000, "Expenses": 7500},
            {"Month": "Feb", "Revenue": 13000, "Expenses": 8500}
        ],
        data_types={"Month": "text", "Revenue": "number", "Expenses": "number"},
        row_count=2,
        column_count=3,
        summary="Monthly financial summary",
        has_dates=False,
        has_numbers=True
    )
    
    # Align sheets
    aligner = SheetAligner()
    aligned_data = aligner.align_sheets(
        sheets=[sheet1, sheet2],
        file_ids=["file1", "file2"]
    )
    
    print(f"Common columns: {aligned_data.common_columns}")
    print(f"Missing columns: {aligned_data.missing_columns}")
    print(f"\nAligned data from file1:")
    for row in aligned_data.file_data.get("file1", []):
        print(f"  {row}")
    print(f"\nAligned data from file2:")
    for row in aligned_data.file_data.get("file2", []):
        print(f"  {row}")


def example_difference_calculation():
    """Example: Calculate differences and trends."""
    print("\n=== Example 3: Difference Calculation ===\n")
    
    from src.models.domain_models import AlignedData
    
    # Create sample aligned data
    aligned_data = AlignedData(
        common_columns=["Month", "Revenue", "Expenses"],
        file_data={
            "file1": [
                {"Month": "Jan", "Revenue": 10000, "Expenses": 7000},
                {"Month": "Feb", "Revenue": 12000, "Expenses": 8000}
            ],
            "file2": [
                {"Month": "Jan", "Revenue": 11000, "Expenses": 7500},
                {"Month": "Feb", "Revenue": 13000, "Expenses": 8500}
            ]
        },
        missing_columns={}
    )
    
    # Calculate differences
    calculator = DifferenceCalculator()
    differences = calculator.calculate_differences(aligned_data)
    
    print("Column Differences:")
    for column, diffs in differences.get("column_differences", {}).items():
        print(f"\n{column}:")
        for comparison, diff_data in diffs.items():
            if isinstance(diff_data, dict):
                print(f"  {comparison}:")
                print(f"    Absolute: {diff_data.get('absolute_difference')}")
                print(f"    Percentage: {diff_data.get('percentage_change')}%")
                print(f"    Trend: {diff_data.get('trend')}")
    
    print("\n\nAggregates:")
    for column, agg in differences.get("aggregates", {}).items():
        print(f"\n{column}:")
        print(f"  Sum: {agg.get('sum')}")
        print(f"  Average: {agg.get('average')}")
        print(f"  Min: {agg.get('min')}")
        print(f"  Max: {agg.get('max')}")
    
    print("\n\nOverall Trends:")
    for column, trend in differences.get("trends", {}).items():
        print(f"  {column}: {trend}")


def example_comparison_formatting():
    """Example: Format comparison results with LLM summary."""
    print("\n=== Example 4: Comparison Formatting ===\n")
    
    from src.models.domain_models import AlignedData
    
    # Initialize services
    config = AppConfig.from_env()
    
    # Create LLM service for summary generation
    llm_service = LLMServiceFactory.create(
        config.llm.provider,
        config.llm.config
    )
    
    # Create cache service for caching aligned data
    cache_service = CacheServiceFactory.create(
        config.cache.provider,
        config.cache.config
    )
    
    # Create formatter
    formatter = ComparisonFormatter(
        llm_service=llm_service,
        cache_service=cache_service
    )
    
    # Sample data
    aligned_data = AlignedData(
        common_columns=["Month", "Revenue", "Expenses"],
        file_data={
            "file1": [
                {"Month": "Jan", "Revenue": 10000, "Expenses": 7000}
            ],
            "file2": [
                {"Month": "Jan", "Revenue": 12000, "Expenses": 8000}
            ]
        },
        missing_columns={}
    )
    
    differences = {
        "column_differences": {
            "Revenue": {
                "file1_vs_file2": {
                    "absolute_difference": 2000,
                    "percentage_change": 20.0,
                    "trend": "increasing"
                }
            }
        },
        "trends": {"Revenue": "increasing", "Expenses": "increasing"},
        "aggregates": {},
        "summary_stats": {"total_files": 2, "total_columns": 3}
    }
    
    # Format comparison
    result = formatter.format_comparison(
        file_ids=["file1", "file2"],
        aligned_data=aligned_data,
        differences=differences,
        query="Compare revenue between files"
    )
    
    print(f"Summary: {result.summary}")
    print(f"\nVisualization data available: {result.visualization_data is not None}")


def example_multi_file_comparison():
    """Example: Compare more than 2 files."""
    print("\n=== Example 5: Multi-File Comparison (3+ files) ===\n")
    
    # Initialize services
    config = AppConfig.from_env()
    auth_service = AuthenticationService()
    gdrive_connector = auth_service.get_authenticated_client()
    content_extractor = ContentExtractor()
    
    # Initialize comparison engine
    comparison_engine = ComparisonEngine(
        gdrive_connector=gdrive_connector,
        content_extractor=content_extractor
    )
    
    # Compare multiple files (up to 5)
    file_ids = [
        "file_id_q1_2024",
        "file_id_q2_2024",
        "file_id_q3_2024",
        "file_id_q4_2024"
    ]
    
    query = "Compare quarterly performance across all quarters of 2024"
    
    try:
        result = comparison_engine.compare_files(
            file_ids=file_ids,
            query=query
        )
        
        print(f"Files compared: {len(result.files_compared)}")
        print(f"\nSummary: {result.summary}")
        
        # Display trends
        if result.differences:
            trends = result.differences.get("trends", {})
            print("\nTrends across quarters:")
            for column, trend in trends.items():
                print(f"  - {column}: {trend}")
        
    except Exception as e:
        print(f"Error during comparison: {str(e)}")


def main():
    """Run all examples."""
    print("=" * 70)
    print("Comparison Engine Usage Examples")
    print("=" * 70)
    
    # Note: Most examples require authentication and actual file IDs
    # Uncomment the examples you want to run
    
    # example_basic_comparison()
    example_sheet_alignment()
    example_difference_calculation()
    # example_comparison_formatting()
    # example_multi_file_comparison()
    
    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
