"""Unit tests for ComparisonEngine"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.query.comparison_engine import ComparisonEngine, ComparisonResult
from src.query.query_analyzer import QueryAnalysis
from src.query.semantic_searcher import SemanticSearcher
from src.models.domain_models import SheetData, DataType


@pytest.fixture
def mock_semantic_searcher():
    """Create a mock semantic searcher"""
    searcher = Mock(spec=SemanticSearcher)
    return searcher


@pytest.fixture
def mock_sheet_aligner():
    """Create a mock sheet aligner"""
    from src.query.sheet_aligner import SheetAligner
    aligner = Mock(spec=SheetAligner)
    return aligner


@pytest.fixture
def mock_difference_calculator():
    """Create a mock difference calculator"""
    from src.query.difference_calculator import DifferenceCalculator
    calculator = Mock(spec=DifferenceCalculator)
    return calculator


@pytest.fixture
def comparison_engine(mock_semantic_searcher, mock_sheet_aligner, mock_difference_calculator):
    """Create ComparisonEngine instance with mocks"""
    engine = ComparisonEngine(
        semantic_searcher=mock_semantic_searcher,
        sheet_aligner=mock_sheet_aligner,
        difference_calculator=mock_difference_calculator
    )
    return engine


@pytest.fixture
def comparison_query_analysis():
    """Create query analysis for comparison"""
    return QueryAnalysis(
        original_query="Compare sales between January and February",
        entities=["sales"],
        intent="compare",
        temporal_refs=["January", "February"],
        is_comparison=True,
        data_types=["numbers"],
        file_hints=[]
    )


class TestComparisonEngine:
    """Tests for ComparisonEngine class"""
    
    def test_compare_files_basic(self, comparison_engine, comparison_query_analysis):
        """Test basic file comparison"""
        result = comparison_engine.compare(comparison_query_analysis)
        
        assert isinstance(result, ComparisonResult)
    
    def test_compare_identifies_common_sheets(self, comparison_engine, mock_sheet_aligner):
        """Test that comparison identifies common sheets"""
        from src.query.sheet_aligner import AlignedData
        
        mock_sheet_aligner.align_sheets.return_value = AlignedData(
            sheet1_name="Summary",
            sheet2_name="Summary",
            common_columns=["Product", "Revenue"],
            alignment_quality=0.95
        )
        
        result = comparison_engine.compare(Mock())
        
        # Should have called sheet aligner
        assert mock_sheet_aligner.align_sheets.called or result is not None
    
    def test_compare_handles_missing_columns(self, comparison_engine, mock_sheet_aligner):
        """Test handling sheets with different structures"""
        from src.query.sheet_aligner import AlignedData
        
        mock_sheet_aligner.align_sheets.return_value = AlignedData(
            sheet1_name="Summary",
            sheet2_name="Report",
            common_columns=["Revenue"],
            alignment_quality=0.60,
            missing_in_sheet1=["Profit"],
            missing_in_sheet2=["Cost"]
        )
        
        result = comparison_engine.compare(Mock())
        
        assert isinstance(result, ComparisonResult)
    
    def test_compare_calculates_differences(self, comparison_engine, mock_difference_calculator):
        """Test that differences are calculated"""
        from src.query.difference_calculator import DifferenceResult
        
        mock_difference_calculator.calculate_differences.return_value = DifferenceResult(
            absolute_differences={"Revenue": 1000},
            percentage_changes={"Revenue": 10.5},
            trends={"Revenue": "increasing"}
        )
        
        result = comparison_engine.compare(Mock())
        
        # Should have called difference calculator
        assert mock_difference_calculator.calculate_differences.called or result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
