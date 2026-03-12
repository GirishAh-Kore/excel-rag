"""Unit tests for SemanticSearcher"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from src.query.semantic_searcher import SemanticSearcher, SearchResults
from src.abstractions.embedding_service import EmbeddingService
from src.indexing.vector_storage import VectorStorageManager


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service"""
    service = Mock(spec=EmbeddingService)
    service.embed_text.return_value = [0.1] * 1536  # Mock embedding vector
    return service


@pytest.fixture
def mock_vector_storage():
    """Create a mock vector storage manager"""
    storage = Mock(spec=VectorStorageManager)
    storage.search.return_value = [
        {
            "id": "file1_sheet1",
            "score": 0.95,
            "metadata": {
                "file_id": "file1",
                "file_name": "Sales_Jan2024.xlsx",
                "sheet_name": "Summary",
                "has_numbers": True
            }
        },
        {
            "id": "file2_sheet1",
            "score": 0.85,
            "metadata": {
                "file_id": "file2",
                "file_name": "Sales_Feb2024.xlsx",
                "sheet_name": "Summary",
                "has_numbers": True
            }
        }
    ]
    return storage


@pytest.fixture
def semantic_searcher(mock_embedding_service, mock_vector_storage):
    """Create SemanticSearcher instance with mocks"""
    return SemanticSearcher(mock_embedding_service, mock_vector_storage)


class TestSemanticSearcher:
    """Tests for SemanticSearcher class"""
    
    def test_search_basic_query(self, semantic_searcher, mock_embedding_service, mock_vector_storage):
        """Test basic semantic search"""
        query = "What is the total sales?"
        
        results = semantic_searcher.search(query, top_k=10)
        
        assert isinstance(results, SearchResults)
        assert len(results.candidates) > 0
        assert mock_embedding_service.embed_text.called
        assert mock_vector_storage.search.called
    
    def test_search_with_filters(self, semantic_searcher, mock_vector_storage):
        """Test search with metadata filters"""
        query = "Show me sales data"
        filters = {"file_name": "Sales_Jan2024.xlsx"}
        
        results = semantic_searcher.search(query, top_k=10, filters=filters)
        
        # Verify filters were passed to vector storage
        call_args = mock_vector_storage.search.call_args
        assert call_args is not None
    
    def test_search_returns_ranked_results(self, semantic_searcher):
        """Test that results are ranked by score"""
        query = "What is the revenue?"
        
        results = semantic_searcher.search(query, top_k=10)
        
        # Results should be sorted by score descending
        scores = [c.score for c in results.candidates]
        assert scores == sorted(scores, reverse=True)
    
    def test_search_with_pivot_tables(self, semantic_searcher, mock_vector_storage):
        """Test searching for pivot table content"""
        mock_vector_storage.search.return_value = [
            {
                "id": "file1_pivot1",
                "score": 0.92,
                "metadata": {
                    "file_id": "file1",
                    "file_name": "Report.xlsx",
                    "sheet_name": "Analysis",
                    "has_pivot_tables": True
                }
            }
        ]
        
        query = "Show me the pivot table analysis"
        results = semantic_searcher.search(query, top_k=5, search_pivots=True)
        
        assert len(results.candidates) > 0
        assert results.candidates[0].metadata.get("has_pivot_tables") is True
    
    def test_search_empty_results(self, semantic_searcher, mock_vector_storage):
        """Test handling empty search results"""
        mock_vector_storage.search.return_value = []
        
        query = "nonexistent data"
        results = semantic_searcher.search(query, top_k=10)
        
        assert isinstance(results, SearchResults)
        assert len(results.candidates) == 0
    
    def test_search_handles_embedding_error(self, semantic_searcher, mock_embedding_service):
        """Test handling embedding service errors"""
        mock_embedding_service.embed_text.side_effect = Exception("Embedding API error")
        
        query = "What is the total?"
        
        with pytest.raises(Exception):
            semantic_searcher.search(query, top_k=10)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
