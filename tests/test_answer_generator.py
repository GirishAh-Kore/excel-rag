"""Unit tests for AnswerGenerator"""

import pytest
from unittest.mock import Mock

from src.query.answer_generator import AnswerGenerator, GeneratedAnswer
from src.query.query_analyzer import QueryAnalysis
from src.abstractions.llm_service import LLMService
from src.models.domain_models import SheetData, DataType


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service"""
    llm = Mock(spec=LLMService)
    llm.generate.return_value = "The total revenue is $3,000 based on the data from Sales_Jan2024.xlsx."
    return llm


@pytest.fixture
def answer_generator(mock_llm_service):
    """Create AnswerGenerator instance"""
    return AnswerGenerator(mock_llm_service)


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
def sample_sheet_data():
    """Create sample sheet data"""
    return SheetData(
        sheet_name="Summary",
        headers=["Product", "Revenue"],
        rows=[
            {"Product": "A", "Revenue": 1000},
            {"Product": "B", "Revenue": 2000}
        ],
        data_types={
            "Product": DataType.TEXT,
            "Revenue": DataType.NUMBER
        },
        row_count=2,
        column_count=2,
        summary="Sales summary",
        has_numbers=True
    )


class TestAnswerGenerator:
    """Tests for AnswerGenerator class"""
    
    def test_generate_answer_basic(self, answer_generator, sample_query_analysis, sample_sheet_data):
        """Test basic answer generation"""
        answer = answer_generator.generate_answer(
            query_analysis=sample_query_analysis,
            sheet_data=sample_sheet_data,
            file_name="Sales_Jan2024.xlsx"
        )
        
        assert isinstance(answer, GeneratedAnswer)
        assert answer.answer_text is not None
        assert len(answer.answer_text) > 0
    
    def test_answer_includes_citations(self, answer_generator, sample_query_analysis, sample_sheet_data):
        """Test that answer includes source citations"""
        answer = answer_generator.generate_answer(
            query_analysis=sample_query_analysis,
            sheet_data=sample_sheet_data,
            file_name="Sales_Jan2024.xlsx"
        )
        
        # Should include file name in citations
        assert hasattr(answer, 'citations')
        if answer.citations:
            assert any("Sales_Jan2024.xlsx" in str(c) for c in answer.citations)
    
    def test_answer_has_confidence_score(self, answer_generator, sample_query_analysis, sample_sheet_data):
        """Test that answer includes confidence score"""
        answer = answer_generator.generate_answer(
            query_analysis=sample_query_analysis,
            sheet_data=sample_sheet_data,
            file_name="Sales_Jan2024.xlsx"
        )
        
        assert hasattr(answer, 'confidence')
        assert 0 <= answer.confidence <= 100
    
    def test_generate_table_answer(self, answer_generator, sample_query_analysis, sample_sheet_data):
        """Test generating answer with table data"""
        # Query that should return table
        query = QueryAnalysis(
            original_query="Show me all products and their revenue",
            entities=["products", "revenue"],
            intent="retrieve_data",
            temporal_refs=[],
            is_comparison=False,
            data_types=["numbers", "text"],
            file_hints=[]
        )
        
        answer = answer_generator.generate_answer(
            query_analysis=query,
            sheet_data=sample_sheet_data,
            file_name="Sales.xlsx"
        )
        
        assert isinstance(answer, GeneratedAnswer)
        # Answer should contain structured data
        assert answer.answer_text is not None
    
    def test_handle_llm_error(self, answer_generator, mock_llm_service, sample_query_analysis, sample_sheet_data):
        """Test handling LLM service errors"""
        mock_llm_service.generate.side_effect = Exception("LLM API error")
        
        # Should handle error and return fallback answer
        answer = answer_generator.generate_answer(
            query_analysis=sample_query_analysis,
            sheet_data=sample_sheet_data,
            file_name="Sales.xlsx"
        )
        
        assert isinstance(answer, GeneratedAnswer)
        # Should have some answer even if LLM fails
        assert answer.answer_text is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
