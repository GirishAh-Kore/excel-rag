"""Unit tests for DataFormatter"""

import pytest
from datetime import datetime

from src.query.data_formatter import DataFormatter
from src.models.domain_models import CellData, DataType


@pytest.fixture
def data_formatter():
    """Create DataFormatter instance"""
    return DataFormatter()


class TestDataFormatter:
    """Tests for DataFormatter class"""
    
    def test_format_number_with_currency(self, data_formatter):
        """Test formatting numbers with currency"""
        cell = CellData(
            value=1234.56,
            data_type=DataType.NUMBER,
            format="$#,##0.00"
        )
        
        formatted = data_formatter.format_cell(cell)
        
        assert "$" in formatted
        assert "1,234.56" in formatted
    
    def test_format_number_with_percentage(self, data_formatter):
        """Test formatting numbers as percentages"""
        cell = CellData(
            value=0.75,
            data_type=DataType.NUMBER,
            format="0.00%"
        )
        
        formatted = data_formatter.format_cell(cell)
        
        assert "%" in formatted
        assert "75" in formatted
    
    def test_format_date(self, data_formatter):
        """Test formatting dates"""
        cell = CellData(
            value=datetime(2024, 1, 15),
            data_type=DataType.DATE,
            format="yyyy-mm-dd"
        )
        
        formatted = data_formatter.format_cell(cell)
        
        assert "2024" in formatted
        assert "01" in formatted or "1" in formatted
        assert "15" in formatted
    
    def test_format_text(self, data_formatter):
        """Test formatting text values"""
        cell = CellData(
            value="Product Name",
            data_type=DataType.TEXT
        )
        
        formatted = data_formatter.format_cell(cell)
        
        assert formatted == "Product Name"
    
    def test_format_table_data(self, data_formatter):
        """Test formatting table data"""
        rows = [
            {"Product": "A", "Revenue": 1000, "Units": 10},
            {"Product": "B", "Revenue": 2000, "Units": 20}
        ]
        
        formatted = data_formatter.format_table(rows, headers=["Product", "Revenue", "Units"])
        
        assert isinstance(formatted, str)
        assert "Product" in formatted
        assert "Revenue" in formatted
        assert "1000" in formatted or "1,000" in formatted
    
    def test_format_formula_explanation(self, data_formatter):
        """Test formatting formula explanations"""
        formula = "=SUM(A1:A10)"
        
        explanation = data_formatter.format_formula(formula)
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        # Should contain some explanation of the formula
        assert "SUM" in explanation or "sum" in explanation.lower()
    
    def test_format_large_numbers(self, data_formatter):
        """Test formatting large numbers with thousands separator"""
        cell = CellData(
            value=1234567.89,
            data_type=DataType.NUMBER,
            format="#,##0.00"
        )
        
        formatted = data_formatter.format_cell(cell)
        
        # Should have thousands separators
        assert "," in formatted
        assert "1,234,567" in formatted
    
    def test_format_empty_value(self, data_formatter):
        """Test formatting empty/null values"""
        cell = CellData(
            value=None,
            data_type=DataType.TEXT
        )
        
        formatted = data_formatter.format_cell(cell)
        
        # Should handle None gracefully
        assert formatted in ["", "N/A", "None", None]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
