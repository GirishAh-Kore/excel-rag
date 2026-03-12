"""Unit tests for QueryAnalyzer"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.query.query_analyzer import QueryAnalyzer, QueryAnalysis
from src.abstractions.llm_service import LLMService


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service"""
    llm = Mock(spec=LLMService)
    llm.generate_structured.return_value = {
        "entities": ["sales", "revenue"],
        "intent": "retrieve_data",
        "temporal_refs": [{"text": "January 2024", "date": "2024-01-01"}],
        "is_comparison": False,
        "data_types_requested": ["numbers"],
        "file_name_hints": []
    }
    return llm


@pytest.fixture
def query_analyzer(mock_llm_service):
    """Create QueryAnalyzer instance with mock LLM"""
    return QueryAnalyzer(mock_llm_service)


class TestQueryAnalyzer:
    """Tests for QueryAnalyzer class"""
    
    def test_analyze_simple_query(self, query_analyzer, mock_llm_service):
        """Test analyzing a simple query"""
        query = "What is the total sales in January?"
        
        result = query_analyzer.analyze(query)
        
        assert isinstance(result, QueryAnalysis)
        assert result.intent is not None
        assert mock_llm_service.generate_structured.called
    
    def test_detect_comparison_query(self, query_analyzer, mock_llm_service):
        """Test detecting comparison queries"""
        mock_llm_service.generate_structured.return_value = {
            "entities": ["sales"],
            "intent": "compare",
            "temporal_refs": [
                {"text": "January", "date": "2024-01-01"},
                {"text": "February", "date": "2024-02-01"}
            ],
            "is_comparison": True,
            "data_types_requested": ["numbers"],
            "file_name_hints": []
        }
        
        query = "Compare sales between January and February"
        result = query_analyzer.analyze(query)
        
        assert result.is_comparison is True
        assert len(result.temporal_refs) == 2
    
    def test_extract_file_hints(self, query_analyzer, mock_llm_service):
        """Test extracting file name hints from query"""
        mock_llm_service.generate_structured.return_value = {
            "entities": ["expenses"],
            "intent": "retrieve_data",
            "temporal_refs": [],
            "is_comparison": False,
            "data_types_requested": ["numbers"],
            "file_name_hints": ["Q1_Report.xlsx"]
        }
        
        query = "What are the expenses in Q1_Report.xlsx?"
        result = query_analyzer.analyze(query)
        
        assert len(result.file_name_hints) > 0
        # File name hints may be extracted without extension
        assert any("Q1_Report" in hint for hint in result.file_name_hints)
    
    def test_identify_data_types(self, query_analyzer, mock_llm_service):
        """Test identifying requested data types"""
        mock_llm_service.generate_structured.return_value = {
            "entities": ["employee", "salary", "hire date"],
            "intent": "retrieve_data",
            "temporal_refs": [],
            "is_comparison": False,
            "data_types_requested": ["text", "numbers", "dates"],
            "file_name_hints": []
        }
        
        query = "Show me employee names, salaries, and hire dates"
        result = query_analyzer.analyze(query)
        
        # Should identify at least some data types
        assert len(result.data_types_requested) > 0
        assert "dates" in result.data_types_requested or "text" in result.data_types_requested
    
    def test_handle_llm_error(self, query_analyzer, mock_llm_service):
        """Test handling LLM service errors"""
        mock_llm_service.generate_structured.side_effect = Exception("LLM API error")
        
        query = "What is the total?"
        
        # Should handle error gracefully and return basic analysis
        result = query_analyzer.analyze(query)
        
        assert isinstance(result, QueryAnalysis)
        assert result.intent is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
