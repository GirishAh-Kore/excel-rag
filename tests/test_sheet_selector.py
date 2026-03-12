"""Unit tests for SheetSelector"""

import pytest
from unittest.mock import Mock

from src.query.sheet_selector import SheetSelector, SheetSelection
from src.query.query_analyzer import QueryAnalysis
from src.models.domain_models import SheetData, DataType


@pytest.fixture
def sheet_selector():
    """Create SheetSelector instance"""
    return SheetSelector()


@pytest.fixture
def sample_sheets():
    """Create sample sheet data"""
    return [
        SheetData(
            sheet_name="Sales Summary",
            headers=["Month", "Product", "Revenue", "Units Sold"],
            rows=[],
            data_types={
                "Month": DataType.TEXT,
                "Product": DataType.TEXT,
                "Revenue": DataType.NUMBER,
                "Units Sold": DataType.NUMBER
            },
            row_count=12,
            column_count=4,
            summary="Monthly sales data by product",
            has_numbers=True,
            has_dates=False
        ),
        SheetData(
            sheet_name="Employee Data",
            headers=["Name", "Department", "Salary", "Hire Date"],
            rows=[],
            data_types={
                "Name": DataType.TEXT,
                "Department": DataType.TEXT,
                "Salary": DataType.NUMBER,
                "Hire Date": DataType.DATE
            },
            row_count=50,
            column_count=4,
            summary="Employee information",
            has_numbers=True,
            has_dates=True
        ),
        SheetData(
            sheet_name="Config",
            headers=["Setting", "Value"],
            rows=[],
            data_types={
                "Setting": DataType.TEXT,
                "Value": DataType.TEXT
            },
            row_count=5,
            column_count=2,
            summary="Configuration settings",
            has_numbers=False,
            has_dates=False
        )
    ]


@pytest.fixture
def sales_query_analysis():
    """Create query analysis for sales query"""
    return QueryAnalysis(
        original_query="What is the total revenue?",
        entities=["revenue", "total"],
        intent="retrieve_data",
        temporal_refs=[],
        is_comparison=False,
        data_types=["numbers"],
        file_hints=[]
    )


class TestSheetSelector:
    """Tests for SheetSelector class"""
    
    def test_select_sheet_by_name_match(self, sheet_selector, sample_sheets, sales_query_analysis):
        """Test selecting sheet by name similarity"""
        selection = sheet_selector.select_sheet(sample_sheets, sales_query_analysis)
        
        assert isinstance(selection, SheetSelection)
        assert selection.selected_sheet is not None
        # Should select "Sales Summary" for revenue query
        assert "Sales" in selection.selected_sheet.sheet_name
    
    def test_select_sheet_by_column_match(self, sheet_selector, sample_sheets):
        """Test selecting sheet by column header match"""
        query = QueryAnalysis(
            original_query="Show me employee salaries",
            entities=["employee", "salary"],
            intent="retrieve_data",
            temporal_refs=[],
            is_comparison=False,
            data_types=["numbers"],
            file_hints=[]
        )
        
        selection = sheet_selector.select_sheet(sample_sheets, query)
        
        assert selection.selected_sheet is not None
        # Should select "Employee Data" sheet
        assert "Employee" in selection.selected_sheet.sheet_name
        assert "Salary" in selection.selected_sheet.headers
    
    def test_select_sheet_by_data_type(self, sheet_selector, sample_sheets):
        """Test selecting sheet by data type alignment"""
        query = QueryAnalysis(
            original_query="Show me dates",
            entities=["dates"],
            intent="retrieve_data",
            temporal_refs=[],
            is_comparison=False,
            data_types=["dates"],
            file_hints=[]
        )
        
        selection = sheet_selector.select_sheet(sample_sheets, query)
        
        assert selection.selected_sheet is not None
        # Should select sheet with dates (Employee Data)
        assert selection.selected_sheet.has_dates is True
    
    def test_select_sheet_confidence_score(self, sheet_selector, sample_sheets, sales_query_analysis):
        """Test that selection includes confidence score"""
        selection = sheet_selector.select_sheet(sample_sheets, sales_query_analysis)
        
        assert hasattr(selection, 'confidence')
        assert 0 <= selection.confidence <= 1
    
    def test_select_multiple_sheets_high_scores(self, sheet_selector, sample_sheets):
        """Test selecting multiple sheets when scores are similar"""
        query = QueryAnalysis(
            original_query="Show me all data",
            entities=["data"],
            intent="retrieve_data",
            temporal_refs=[],
            is_comparison=False,
            data_types=["numbers"],
            file_hints=[]
        )
        
        selection = sheet_selector.select_multiple_sheets(sample_sheets, query, threshold=0.5)
        
        assert isinstance(selection.selected_sheets, list)
        # Should select sheets with numbers
        assert len(selection.selected_sheets) >= 1
    
    def test_no_good_match_returns_best_available(self, sheet_selector, sample_sheets):
        """Test that best sheet is returned even with low confidence"""
        query = QueryAnalysis(
            original_query="Show me xyz data",
            entities=["xyz"],
            intent="retrieve_data",
            temporal_refs=[],
            is_comparison=False,
            data_types=[],
            file_hints=[]
        )
        
        selection = sheet_selector.select_sheet(sample_sheets, query)
        
        # Should still return a sheet (best available)
        assert selection.selected_sheet is not None
        # But confidence should be lower
        assert selection.confidence < 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
