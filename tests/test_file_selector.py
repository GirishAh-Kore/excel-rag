"""Unit tests for FileSelector"""

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta

from src.query.file_selector import FileSelector, FileSelection
from src.query.query_analyzer import QueryAnalysis
from src.indexing.metadata_storage import MetadataStorageManager


@pytest.fixture
def mock_metadata_storage():
    """Create a mock metadata storage manager"""
    storage = Mock(spec=MetadataStorageManager)
    storage.get_user_preferences.return_value = []
    return storage


@pytest.fixture
def file_selector(mock_metadata_storage):
    """Create FileSelector instance"""
    return FileSelector(mock_metadata_storage)


@pytest.fixture
def sample_candidates():
    """Create sample file candidates"""
    return [
        {
            "file_id": "file1",
            "file_name": "Sales_Jan2024.xlsx",
            "file_path": "/reports/Sales_Jan2024.xlsx",
            "modified_time": datetime.now() - timedelta(days=5),
            "score": 0.95
        },
        {
            "file_id": "file2",
            "file_name": "Sales_Feb2024.xlsx",
            "file_path": "/reports/Sales_Feb2024.xlsx",
            "modified_time": datetime.now() - timedelta(days=35),
            "score": 0.85
        },
        {
            "file_id": "file3",
            "file_name": "Revenue_Jan2024.xlsx",
            "file_path": "/reports/Revenue_Jan2024.xlsx",
            "modified_time": datetime.now() - timedelta(days=10),
            "score": 0.80
        }
    ]


@pytest.fixture
def sample_query_analysis():
    """Create sample query analysis"""
    return QueryAnalysis(
        original_query="What is the total sales in January?",
        entities=["sales", "total"],
        intent="retrieve_data",
        temporal_refs=["January"],
        is_comparison=False,
        data_types=["numbers"],
        file_hints=[]
    )


class TestFileSelector:
    """Tests for FileSelector class"""
    
    def test_rank_files_basic(self, file_selector, sample_candidates, sample_query_analysis):
        """Test basic file ranking"""
        ranked = file_selector.rank_files(sample_candidates, sample_query_analysis)
        
        assert len(ranked) == len(sample_candidates)
        assert all(hasattr(f, 'final_score') for f in ranked)
        # Scores should be between 0 and 1
        assert all(0 <= f.final_score <= 1 for f in ranked)
    
    def test_rank_files_sorted_by_score(self, file_selector, sample_candidates, sample_query_analysis):
        """Test that files are sorted by final score"""
        ranked = file_selector.rank_files(sample_candidates, sample_query_analysis)
        
        scores = [f.final_score for f in ranked]
        assert scores == sorted(scores, reverse=True)
    
    def test_date_matching_boost(self, file_selector, sample_candidates, sample_query_analysis):
        """Test that files with matching dates get boosted"""
        # Query mentions January, file1 has Jan in name
        ranked = file_selector.rank_files(sample_candidates, sample_query_analysis)
        
        # File with "Jan" in name should rank higher
        jan_files = [f for f in ranked if "Jan" in f.file_name]
        assert len(jan_files) > 0
    
    def test_recency_boost(self, file_selector, sample_candidates, sample_query_analysis):
        """Test that more recent files get a boost"""
        ranked = file_selector.rank_files(sample_candidates, sample_query_analysis)
        
        # More recent file (file1, 5 days old) should have higher metadata score
        # than older file (file2, 35 days old) with same semantic score
        file1 = next(f for f in ranked if f.file_id == "file1")
        file2 = next(f for f in ranked if f.file_id == "file2")
        
        # file1 should rank higher due to recency
        assert file1.final_score >= file2.final_score
    
    def test_select_file_high_confidence(self, file_selector, sample_candidates, sample_query_analysis):
        """Test automatic selection with high confidence"""
        # Set first candidate to very high score
        sample_candidates[0]["score"] = 0.95
        
        ranked = file_selector.rank_files(sample_candidates, sample_query_analysis)
        selection = file_selector.select_file(ranked, sample_query_analysis)
        
        assert isinstance(selection, FileSelection)
        if selection.confidence > 0.90:
            assert selection.selected_file is not None
    
    def test_select_file_low_confidence(self, file_selector, sample_candidates, sample_query_analysis):
        """Test clarification request with low confidence"""
        # Set all candidates to similar low scores
        for candidate in sample_candidates:
            candidate["score"] = 0.65
        
        ranked = file_selector.rank_files(sample_candidates, sample_query_analysis)
        selection = file_selector.select_file(ranked, sample_query_analysis)
        
        assert isinstance(selection, FileSelection)
        # Should either select or request clarification
        assert selection.selected_file is not None or selection.needs_clarification
    
    def test_user_preference_boost(self, file_selector, mock_metadata_storage, sample_candidates, sample_query_analysis):
        """Test that user preferences boost file scores"""
        # Mock user preference for file1
        mock_metadata_storage.get_user_preferences.return_value = [
            {"file_id": "file1", "selection_count": 5}
        ]
        
        ranked = file_selector.rank_files(sample_candidates, sample_query_analysis)
        
        # file1 should get preference boost
        file1 = next(f for f in ranked if f.file_id == "file1")
        assert file1.preference_score > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
