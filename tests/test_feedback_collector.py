"""
Tests for FeedbackCollector

Tests the feedback collection, aggregation, and flagging functionality
for chunk quality feedback.

Requirements: 27.1, 27.2, 27.3, 27.4, 27.5
"""

import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from src.chunk_viewer.feedback import (
    FeedbackCollector,
    FeedbackRecord,
    FeedbackType,
    SQLiteFeedbackStore,
    ChunkFeedbackSummary,
    FeedbackAggregation,
)
from src.exceptions import ChunkViewerError
from src.models.chunk_visibility import ChunkFeedback


class TestFeedbackType:
    """Tests for FeedbackType enum."""
    
    def test_feedback_types_exist(self):
        """Test all required feedback types are defined."""
        assert FeedbackType.INCORRECT_DATA.value == "incorrect_data"
        assert FeedbackType.MISSING_DATA.value == "missing_data"
        assert FeedbackType.WRONG_BOUNDARIES.value == "wrong_boundaries"
        assert FeedbackType.EXTRACTION_ERROR.value == "extraction_error"
        assert FeedbackType.OTHER.value == "other"


class TestFeedbackRecord:
    """Tests for FeedbackRecord dataclass."""
    
    def test_create_feedback_record(self):
        """Test creating a feedback record."""
        record = FeedbackRecord(
            feedback_id="fb_123",
            chunk_id="chunk_001",
            feedback_type="incorrect_data",
            rating=2,
            comment="Data is wrong",
            user_id="user_001",
            created_at=datetime.now(),
        )
        
        assert record.feedback_id == "fb_123"
        assert record.chunk_id == "chunk_001"
        assert record.feedback_type == "incorrect_data"
        assert record.rating == 2
        assert record.comment == "Data is wrong"
        assert record.user_id == "user_001"


class TestSQLiteFeedbackStore:
    """Tests for SQLiteFeedbackStore."""
    
    def test_init_requires_db_connection(self):
        """Test that initialization requires a database connection."""
        with pytest.raises(ChunkViewerError) as exc_info:
            SQLiteFeedbackStore(None)
        
        assert "Database connection is required" in str(exc_info.value)
    
    def test_save_feedback(self):
        """Test saving feedback to the store."""
        mock_db = MagicMock()
        store = SQLiteFeedbackStore(mock_db)
        
        record = FeedbackRecord(
            feedback_id="fb_123",
            chunk_id="chunk_001",
            feedback_type="incorrect_data",
            rating=2,
            comment="Test comment",
            user_id="user_001",
            created_at=datetime.now(),
        )
        
        result = store.save_feedback(record)
        
        assert result == "fb_123"
        mock_db.execute_insert.assert_called_once()
    
    def test_get_feedback_for_chunk(self):
        """Test retrieving feedback for a chunk."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [
            {
                "id": 1,
                "chunk_id": "chunk_001",
                "feedback_type": "incorrect_data",
                "rating": 2,
                "comment": "Test",
                "user_id": "user_001",
                "created_at": "2024-01-01T12:00:00",
            }
        ]
        
        store = SQLiteFeedbackStore(mock_db)
        records = store.get_feedback_for_chunk("chunk_001")
        
        assert len(records) == 1
        assert records[0].chunk_id == "chunk_001"
        assert records[0].feedback_type == "incorrect_data"
    
    def test_get_negative_feedback_count(self):
        """Test counting negative feedback."""
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [{"count": 3}]
        
        store = SQLiteFeedbackStore(mock_db)
        count = store.get_negative_feedback_count("chunk_001")
        
        assert count == 3


class TestFeedbackCollector:
    """Tests for FeedbackCollector."""
    
    @pytest.fixture
    def mock_store(self):
        """Create a mock feedback store."""
        store = MagicMock(spec=SQLiteFeedbackStore)
        store.db_connection = MagicMock()
        return store
    
    @pytest.fixture
    def collector(self, mock_store):
        """Create a FeedbackCollector with mock store."""
        return FeedbackCollector(mock_store)
    
    def test_init_requires_feedback_store(self):
        """Test that initialization requires a feedback store."""
        with pytest.raises(ChunkViewerError) as exc_info:
            FeedbackCollector(None)
        
        assert "Feedback store is required" in str(exc_info.value)
    
    def test_submit_feedback_valid(self, collector, mock_store):
        """Test submitting valid feedback."""
        mock_store.get_negative_feedback_count.return_value = 0
        
        result = collector.submit_feedback(
            chunk_id="chunk_001",
            feedback_type="incorrect_data",
            rating=3,
            comment="Test feedback",
            user_id="user_001",
        )
        
        assert result.chunk_id == "chunk_001"
        assert result.feedback_type == "incorrect_data"
        assert result.rating == 3
        mock_store.save_feedback.assert_called_once()
    
    def test_submit_feedback_invalid_type(self, collector):
        """Test submitting feedback with invalid type."""
        with pytest.raises(ChunkViewerError) as exc_info:
            collector.submit_feedback(
                chunk_id="chunk_001",
                feedback_type="invalid_type",
                rating=3,
            )
        
        assert "Invalid feedback type" in str(exc_info.value)
    
    def test_submit_feedback_invalid_rating_low(self, collector):
        """Test submitting feedback with rating too low."""
        with pytest.raises(ChunkViewerError) as exc_info:
            collector.submit_feedback(
                chunk_id="chunk_001",
                feedback_type="incorrect_data",
                rating=0,
            )
        
        assert "Rating must be between 1 and 5" in str(exc_info.value)
    
    def test_submit_feedback_invalid_rating_high(self, collector):
        """Test submitting feedback with rating too high."""
        with pytest.raises(ChunkViewerError) as exc_info:
            collector.submit_feedback(
                chunk_id="chunk_001",
                feedback_type="incorrect_data",
                rating=6,
            )
        
        assert "Rating must be between 1 and 5" in str(exc_info.value)
    
    def test_submit_feedback_empty_chunk_id(self, collector):
        """Test submitting feedback with empty chunk_id."""
        with pytest.raises(ChunkViewerError) as exc_info:
            collector.submit_feedback(
                chunk_id="",
                feedback_type="incorrect_data",
                rating=3,
            )
        
        assert "chunk_id is required" in str(exc_info.value)
    
    def test_submit_feedback_flags_chunk_on_multiple_negative(self, collector, mock_store):
        """Test that chunk is flagged after multiple negative reports."""
        mock_store.get_negative_feedback_count.return_value = 2
        
        collector.submit_feedback(
            chunk_id="chunk_001",
            feedback_type="incorrect_data",
            rating=1,
        )
        
        # Verify negative count was checked
        mock_store.get_negative_feedback_count.assert_called_with("chunk_001")
    
    def test_submit_feedback_from_model(self, collector, mock_store):
        """Test submitting feedback using ChunkFeedback model."""
        mock_store.get_negative_feedback_count.return_value = 0
        
        feedback_model = ChunkFeedback(
            chunk_id="chunk_001",
            feedback_type="missing_data",
            rating=2,
            comment="Missing rows",
            user_id="user_001",
        )
        
        result = collector.submit_feedback_from_model(feedback_model)
        
        assert result.chunk_id == "chunk_001"
        assert result.feedback_type == "missing_data"
        assert result.rating == 2
    
    def test_get_chunk_feedback_summary_no_feedback(self, collector, mock_store):
        """Test getting summary for chunk with no feedback."""
        mock_store.get_feedback_for_chunk.return_value = []
        
        summary = collector.get_chunk_feedback_summary("chunk_001")
        
        assert summary.chunk_id == "chunk_001"
        assert summary.total_feedback_count == 0
        assert summary.average_rating == 0.0
        assert summary.flagged_for_review is False
    
    def test_get_chunk_feedback_summary_with_feedback(self, collector, mock_store):
        """Test getting summary for chunk with feedback."""
        mock_store.get_feedback_for_chunk.return_value = [
            FeedbackRecord(
                feedback_id="fb_1",
                chunk_id="chunk_001",
                feedback_type="incorrect_data",
                rating=2,
                comment=None,
                user_id=None,
                created_at=datetime(2024, 1, 1, 12, 0, 0),
            ),
            FeedbackRecord(
                feedback_id="fb_2",
                chunk_id="chunk_001",
                feedback_type="incorrect_data",
                rating=1,
                comment=None,
                user_id=None,
                created_at=datetime(2024, 1, 2, 12, 0, 0),
            ),
        ]
        
        summary = collector.get_chunk_feedback_summary("chunk_001")
        
        assert summary.chunk_id == "chunk_001"
        assert summary.total_feedback_count == 2
        assert summary.average_rating == 1.5
        assert summary.negative_count == 2
        assert summary.flagged_for_review is True
        assert summary.feedback_by_type["incorrect_data"] == 2
    
    def test_is_chunk_flagged_true(self, collector, mock_store):
        """Test checking if chunk is flagged when it should be."""
        mock_store.get_negative_feedback_count.return_value = 3
        
        result = collector.is_chunk_flagged("chunk_001")
        
        assert result is True
    
    def test_is_chunk_flagged_false(self, collector, mock_store):
        """Test checking if chunk is flagged when it shouldn't be."""
        mock_store.get_negative_feedback_count.return_value = 1
        
        result = collector.is_chunk_flagged("chunk_001")
        
        assert result is False
    
    def test_get_flagged_chunks(self, collector, mock_store):
        """Test getting all flagged chunks."""
        mock_store.db_connection.execute_query.return_value = [
            {"chunk_id": "chunk_001"},
            {"chunk_id": "chunk_002"},
        ]
        
        result = collector.get_flagged_chunks()
        
        assert len(result) == 2
        assert "chunk_001" in result
        assert "chunk_002" in result
    
    def test_get_feedback_aggregation(self, collector, mock_store):
        """Test getting aggregated feedback statistics."""
        mock_store.get_aggregated_stats.return_value = {
            "total_feedback_count": 10,
            "total_chunks_with_feedback": 5,
            "average_rating": 3.5,
            "feedback_by_type": {"incorrect_data": 4, "missing_data": 6},
            "chunks_flagged_for_review": 2,
        }
        mock_store.db_connection.execute_query.return_value = [
            {"chunk_id": "chunk_001"},
        ]
        
        result = collector.get_feedback_aggregation()
        
        assert result.total_feedback_count == 10
        assert result.total_chunks_with_feedback == 5
        assert result.average_rating == 3.5
        assert result.chunks_flagged_for_review == 2
    
    def test_get_feedback_summary(self, collector, mock_store):
        """Test getting feedback summary for API response."""
        mock_store.get_aggregated_stats.return_value = {
            "total_feedback_count": 10,
            "total_chunks_with_feedback": 5,
            "average_rating": 3.5,
            "feedback_by_type": {"incorrect_data": 4},
            "chunks_flagged_for_review": 2,
        }
        mock_store.db_connection.execute_query.return_value = []
        
        result = collector.get_feedback_summary()
        
        assert "total_feedback_count" in result
        assert "average_rating" in result
        assert "generated_at" in result
    
    def test_custom_negative_threshold(self, mock_store):
        """Test using custom negative threshold."""
        collector = FeedbackCollector(mock_store, negative_threshold=5)
        mock_store.get_negative_feedback_count.return_value = 4
        
        result = collector.is_chunk_flagged("chunk_001")
        
        assert result is False
        
        mock_store.get_negative_feedback_count.return_value = 5
        result = collector.is_chunk_flagged("chunk_001")
        
        assert result is True


class TestFeedbackValidTypes:
    """Tests for valid feedback types constant."""
    
    def test_all_feedback_types_in_valid_set(self):
        """Test all FeedbackType enum values are in VALID_FEEDBACK_TYPES."""
        valid_types = FeedbackCollector.VALID_FEEDBACK_TYPES
        
        for feedback_type in FeedbackType:
            assert feedback_type.value in valid_types
