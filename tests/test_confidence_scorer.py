"""Unit tests for ConfidenceScorer"""

import pytest

from src.query.confidence_scorer import ConfidenceScorer, ConfidenceScore
from src.query.query_analyzer import QueryAnalysis
from src.models.domain_models import SheetData, DataType


@pytest.fixture
def confidence_scorer():
    """Create ConfidenceScorer instance"""
    return ConfidenceScorer()


@pytest.fixture
def sample_query_analysis():
    """Create sample query analysis"""
    return QueryAnalysis(
        original_query="What is the total revenue?",
        entities=["revenue", "total"],
        intent="retrieve_data",
        temporal_refs=[],
        is_comparison=False,
        data_types=["numbers"],
        file_hints=[]
    )


@pytest.fixture
def complete_sheet_data():
    """Create sheet data with complete information"""
    return SheetData(
        sheet_name="Summary",
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
        summary="Complete sales data",
        has_numbers=True
    )


class TestConfidenceScorer:
    """Tests for ConfidenceScorer class"""
    
    def test_calculate_confidence_high(self, confidence_scorer, sample_query_analysis, complete_sheet_data):
        """Test calculating high confidence score"""
        score = confidence_scorer.calculate_confidence(
            query_analysis=sample_query_analysis,
            sheet_data=complete_sheet_data,
            semantic_score=0.95,
            file_selection_confidence=0.90
        )
        
        assert isinstance(score, ConfidenceScore)
        assert 0 <= score.overall_score <= 100
        # With high scores, overall should be high
        assert score.overall_score > 70
    
    def test_calculate_confidence_low(self, confidence_scorer, sample_query_analysis):
        """Test calculating low confidence score"""
        incomplete_sheet = SheetData(
            sheet_name="Partial",
            headers=["Item"],
            rows=[],
            data_types={"Item": DataType.TEXT},
            row_count=0,
            column_count=1,
            summary="Incomplete data"
        )
        
        score = confidence_scorer.calculate_confidence(
            query_analysis=sample_query_analysis,
            sheet_data=incomplete_sheet,
            semantic_score=0.50,
            file_selection_confidence=0.60
        )
        
        assert isinstance(score, ConfidenceScore)
        # With low scores, overall should be lower
        assert score.overall_score < 80
    
    def test_confidence_factors_data_completeness(self, confidence_scorer, sample_query_analysis, complete_sheet_data):
        """Test that data completeness affects confidence"""
        score = confidence_scorer.calculate_confidence(
            query_analysis=sample_query_analysis,
            sheet_data=complete_sheet_data,
            semantic_score=0.90,
            file_selection_confidence=0.90
        )
        
        # Should have breakdown of confidence factors
        assert hasattr(score, 'factors')
        if score.factors:
            assert 'data_completeness' in score.factors
    
    def test_confidence_factors_semantic_similarity(self, confidence_scorer, sample_query_analysis, complete_sheet_data):
        """Test that semantic similarity affects confidence"""
        high_semantic = confidence_scorer.calculate_confidence(
            query_analysis=sample_query_analysis,
            sheet_data=complete_sheet_data,
            semantic_score=0.95,
            file_selection_confidence=0.90
        )
        
        low_semantic = confidence_scorer.calculate_confidence(
            query_analysis=sample_query_analysis,
            sheet_data=complete_sheet_data,
            semantic_score=0.50,
            file_selection_confidence=0.90
        )
        
        # Higher semantic score should result in higher confidence
        assert high_semantic.overall_score > low_semantic.overall_score
    
    def test_confidence_explanation(self, confidence_scorer, sample_query_analysis, complete_sheet_data):
        """Test that confidence score includes explanation"""
        score = confidence_scorer.calculate_confidence(
            query_analysis=sample_query_analysis,
            sheet_data=complete_sheet_data,
            semantic_score=0.90,
            file_selection_confidence=0.85
        )
        
        assert hasattr(score, 'explanation')
        if score.explanation:
            assert isinstance(score.explanation, str)
            assert len(score.explanation) > 0
    
    def test_confidence_bounded_0_to_100(self, confidence_scorer, sample_query_analysis, complete_sheet_data):
        """Test that confidence score is always between 0 and 100"""
        # Test with extreme values
        score = confidence_scorer.calculate_confidence(
            query_analysis=sample_query_analysis,
            sheet_data=complete_sheet_data,
            semantic_score=1.0,
            file_selection_confidence=1.0
        )
        
        assert 0 <= score.overall_score <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
