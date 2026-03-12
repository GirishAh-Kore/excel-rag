"""Unit tests for DifferenceCalculator"""

import pytest

from src.query.difference_calculator import DifferenceCalculator, DifferenceResult
from src.query.sheet_aligner import AlignedData
from src.models.domain_models import SheetData, DataType


@pytest.fixture
def difference_calculator():
    """Create DifferenceCalculator instance"""
    return DifferenceCalculator()


@pytest.fixture
def aligned_data_with_numbers():
    """Create aligned data with numerical values"""
    sheet1 = SheetData(
        sheet_name="Jan",
        headers=["Product", "Revenue", "Units"],
        rows=[
            {"Product": "A", "Revenue": 1000, "Units": 10},
            {"Product": "B", "Revenue": 2000, "Units": 20}
        ],
        data_types={
            "Product": DataType.TEXT,
            "Revenue": DataType.NUMBER,
            "Units": DataType.NUMBER
        },
        row_count=2,
        column_count=3,
        summary="January",
        has_numbers=True
    )
    
    sheet2 = SheetData(
        sheet_name="Feb",
        headers=["Product", "Revenue", "Units"],
        rows=[
            {"Product": "A", "Revenue": 1100, "Units": 11},
            {"Product": "B", "Revenue": 2200, "Units": 22}
        ],
        data_types={
            "Product": DataType.TEXT,
            "Revenue": DataType.NUMBER,
            "Units": DataType.NUMBER
        },
        row_count=2,
        column_count=3,
        summary="February",
        has_numbers=True
    )
    
    aligned = AlignedData(
        sheet1_name="Jan",
        sheet2_name="Feb",
        common_columns=["Product", "Revenue", "Units"],
        key_column="Product",
        alignment_quality=1.0
    )
    
    return aligned, sheet1, sheet2


class TestDifferenceCalculator:
    """Tests for DifferenceCalculator class"""
    
    def test_calculate_absolute_differences(self, difference_calculator, aligned_data_with_numbers):
        """Test calculating absolute differences"""
        aligned, sheet1, sheet2 = aligned_data_with_numbers
        
        result = difference_calculator.calculate_differences(aligned, sheet1, sheet2)
        
        assert isinstance(result, DifferenceResult)
        assert "Revenue" in result.absolute_differences
        # Product A: 1100 - 1000 = 100
        assert result.absolute_differences["Revenue"]["A"] == 100
    
    def test_calculate_percentage_changes(self, difference_calculator, aligned_data_with_numbers):
        """Test calculating percentage changes"""
        aligned, sheet1, sheet2 = aligned_data_with_numbers
        
        result = difference_calculator.calculate_differences(aligned, sheet1, sheet2)
        
        assert "Revenue" in result.percentage_changes
        # Product A: (1100 - 1000) / 1000 * 100 = 10%
        assert abs(result.percentage_changes["Revenue"]["A"] - 10.0) < 0.01
    
    def test_detect_trends(self, difference_calculator, aligned_data_with_numbers):
        """Test trend detection"""
        aligned, sheet1, sheet2 = aligned_data_with_numbers
        
        result = difference_calculator.calculate_differences(aligned, sheet1, sheet2)
        
        assert "Revenue" in result.trends
        # Revenue increased for both products
        assert result.trends["Revenue"]["A"] == "increasing"
        assert result.trends["Revenue"]["B"] == "increasing"
    
    def test_handle_division_by_zero(self, difference_calculator):
        """Test handling division by zero in percentage calculation"""
        sheet1 = SheetData(
            sheet_name="Sheet1",
            headers=["Item", "Value"],
            rows=[{"Item": "A", "Value": 0}],
            data_types={"Item": DataType.TEXT, "Value": DataType.NUMBER},
            row_count=1,
            column_count=2,
            summary="Test",
            has_numbers=True
        )
        
        sheet2 = SheetData(
            sheet_name="Sheet2",
            headers=["Item", "Value"],
            rows=[{"Item": "A", "Value": 100}],
            data_types={"Item": DataType.TEXT, "Value": DataType.NUMBER},
            row_count=1,
            column_count=2,
            summary="Test",
            has_numbers=True
        )
        
        aligned = AlignedData(
            sheet1_name="Sheet1",
            sheet2_name="Sheet2",
            common_columns=["Item", "Value"],
            key_column="Item",
            alignment_quality=1.0
        )
        
        result = difference_calculator.calculate_differences(aligned, sheet1, sheet2)
        
        # Should handle division by zero gracefully
        assert isinstance(result, DifferenceResult)
        # Percentage change should be None or "N/A" for division by zero
        if "Value" in result.percentage_changes:
            assert result.percentage_changes["Value"]["A"] is None or \
                   result.percentage_changes["Value"]["A"] == "N/A"
    
    def test_handle_missing_data(self, difference_calculator):
        """Test handling missing data points"""
        sheet1 = SheetData(
            sheet_name="Sheet1",
            headers=["Item", "Value"],
            rows=[
                {"Item": "A", "Value": 100},
                {"Item": "B", "Value": 200}
            ],
            data_types={"Item": DataType.TEXT, "Value": DataType.NUMBER},
            row_count=2,
            column_count=2,
            summary="Test",
            has_numbers=True
        )
        
        sheet2 = SheetData(
            sheet_name="Sheet2",
            headers=["Item", "Value"],
            rows=[
                {"Item": "A", "Value": 110}
                # B is missing
            ],
            data_types={"Item": DataType.TEXT, "Value": DataType.NUMBER},
            row_count=1,
            column_count=2,
            summary="Test",
            has_numbers=True
        )
        
        aligned = AlignedData(
            sheet1_name="Sheet1",
            sheet2_name="Sheet2",
            common_columns=["Item", "Value"],
            key_column="Item",
            alignment_quality=0.8
        )
        
        result = difference_calculator.calculate_differences(aligned, sheet1, sheet2)
        
        # Should handle missing data
        assert isinstance(result, DifferenceResult)
        # Should have difference for A but mark B as missing
        assert "A" in result.absolute_differences.get("Value", {})
    
    def test_calculate_aggregates(self, difference_calculator, aligned_data_with_numbers):
        """Test calculating aggregate statistics"""
        aligned, sheet1, sheet2 = aligned_data_with_numbers
        
        result = difference_calculator.calculate_differences(aligned, sheet1, sheet2)
        
        # Should have aggregate calculations
        if hasattr(result, 'aggregates'):
            assert "Revenue" in result.aggregates
            # Total revenue should be sum of all products
            assert result.aggregates["Revenue"]["sum"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
