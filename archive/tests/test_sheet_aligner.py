"""Unit tests for SheetAligner"""

import pytest

from src.query.sheet_aligner import SheetAligner, AlignedData
from src.models.domain_models import SheetData, DataType


@pytest.fixture
def sheet_aligner():
    """Create SheetAligner instance"""
    return SheetAligner()


@pytest.fixture
def matching_sheets():
    """Create sheets with matching structure"""
    sheet1 = SheetData(
        sheet_name="Jan_Summary",
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
        summary="January sales",
        has_numbers=True
    )
    
    sheet2 = SheetData(
        sheet_name="Feb_Summary",
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
        summary="February sales",
        has_numbers=True
    )
    
    return sheet1, sheet2


@pytest.fixture
def mismatched_sheets():
    """Create sheets with different structures"""
    sheet1 = SheetData(
        sheet_name="Sales",
        headers=["Product", "Revenue", "Cost"],
        rows=[],
        data_types={
            "Product": DataType.TEXT,
            "Revenue": DataType.NUMBER,
            "Cost": DataType.NUMBER
        },
        row_count=5,
        column_count=3,
        summary="Sales data",
        has_numbers=True
    )
    
    sheet2 = SheetData(
        sheet_name="Report",
        headers=["Item", "Revenue", "Profit"],
        rows=[],
        data_types={
            "Item": DataType.TEXT,
            "Revenue": DataType.NUMBER,
            "Profit": DataType.NUMBER
        },
        row_count=5,
        column_count=3,
        summary="Report data",
        has_numbers=True
    )
    
    return sheet1, sheet2


class TestSheetAligner:
    """Tests for SheetAligner class"""
    
    def test_align_matching_sheets(self, sheet_aligner, matching_sheets):
        """Test aligning sheets with identical structure"""
        sheet1, sheet2 = matching_sheets
        
        aligned = sheet_aligner.align_sheets(sheet1, sheet2)
        
        assert isinstance(aligned, AlignedData)
        assert len(aligned.common_columns) == 3
        assert "Product" in aligned.common_columns
        assert "Revenue" in aligned.common_columns
        assert aligned.alignment_quality > 0.9
    
    def test_align_identifies_key_columns(self, sheet_aligner, matching_sheets):
        """Test identification of key columns for alignment"""
        sheet1, sheet2 = matching_sheets
        
        aligned = sheet_aligner.align_sheets(sheet1, sheet2)
        
        # Should identify "Product" as key column
        assert aligned.key_column is not None
        assert aligned.key_column in ["Product", "product"]
    
    def test_align_mismatched_sheets(self, sheet_aligner, mismatched_sheets):
        """Test aligning sheets with different structures"""
        sheet1, sheet2 = mismatched_sheets
        
        aligned = sheet_aligner.align_sheets(sheet1, sheet2)
        
        assert isinstance(aligned, AlignedData)
        # Should find "Revenue" as common column
        assert "Revenue" in aligned.common_columns
        # Should identify missing columns
        assert len(aligned.missing_in_sheet1) > 0 or len(aligned.missing_in_sheet2) > 0
        # Alignment quality should be lower
        assert aligned.alignment_quality < 1.0
    
    def test_fuzzy_column_matching(self, sheet_aligner):
        """Test fuzzy matching of similar column names"""
        sheet1 = SheetData(
            sheet_name="Sheet1",
            headers=["Product Name", "Total Revenue"],
            rows=[],
            data_types={},
            row_count=5,
            column_count=2,
            summary="Test"
        )
        
        sheet2 = SheetData(
            sheet_name="Sheet2",
            headers=["Product", "Revenue"],
            rows=[],
            data_types={},
            row_count=5,
            column_count=2,
            summary="Test"
        )
        
        aligned = sheet_aligner.align_sheets(sheet1, sheet2)
        
        # Should match similar columns with fuzzy matching
        assert len(aligned.common_columns) > 0
    
    def test_align_empty_sheets(self, sheet_aligner):
        """Test aligning empty sheets"""
        sheet1 = SheetData(
            sheet_name="Empty1",
            headers=[],
            rows=[],
            data_types={},
            row_count=0,
            column_count=0,
            summary="Empty"
        )
        
        sheet2 = SheetData(
            sheet_name="Empty2",
            headers=[],
            rows=[],
            data_types={},
            row_count=0,
            column_count=0,
            summary="Empty"
        )
        
        aligned = sheet_aligner.align_sheets(sheet1, sheet2)
        
        assert isinstance(aligned, AlignedData)
        assert len(aligned.common_columns) == 0
        assert aligned.alignment_quality == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
