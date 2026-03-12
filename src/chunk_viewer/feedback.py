"""
Feedback Collector for Chunk Quality

This module provides feedback collection and aggregation for chunk quality.
It supports feedback submission, aggregation, summary generation, and
flagging chunks with multiple negative reports.

Key Features:
- Submit feedback with types: incorrect_data, missing_data, wrong_boundaries, extraction_error, other
- Aggregate feedback to identify recurring issues
- Generate feedback summaries and statistics
- Flag chunks with multiple negative reports for review

Requirements: 27.1, 27.2, 27.3, 27.4, 27.5
"""

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple

from src.database.connection import DatabaseConnection
from src.exceptions import ChunkViewerError
from src.models.chunk_visibility import ChunkFeedback

logger = logging.getLogger(__name__)


class FeedbackType(str, Enum):
    """
    Types of feedback that can be submitted for chunks.
    
    Requirements: 27.2
    """
    INCORRECT_DATA = "incorrect_data"
    MISSING_DATA = "missing_data"
    WRONG_BOUNDARIES = "wrong_boundaries"
    EXTRACTION_ERROR = "extraction_error"
    OTHER = "other"


@dataclass
class FeedbackRecord:
    """
    A stored feedback record with metadata.
    
    Attributes:
        feedback_id: Unique identifier for the feedback.
        chunk_id: ID of the chunk this feedback is for.
        feedback_type: Type of feedback (from FeedbackType enum).
        rating: Quality rating from 1 (poor) to 5 (excellent).
        comment: Optional detailed comment.
        user_id: Optional user ID who submitted the feedback.
        created_at: Timestamp when feedback was submitted.
    """
    feedback_id: str
    chunk_id: str
    feedback_type: str
    rating: int
    comment: Optional[str]
    user_id: Optional[str]
    created_at: datetime


@dataclass
class ChunkFeedbackSummary:
    """
    Summary of feedback for a specific chunk.
    
    Attributes:
        chunk_id: ID of the chunk.
        total_feedback_count: Total number of feedback submissions.
        average_rating: Average rating across all feedback.
        feedback_by_type: Count of feedback by type.
        negative_count: Count of negative feedback (rating <= 2).
        flagged_for_review: Whether chunk is flagged for review.
        latest_feedback_at: Timestamp of most recent feedback.
    """
    chunk_id: str
    total_feedback_count: int
    average_rating: float
    feedback_by_type: Dict[str, int]
    negative_count: int
    flagged_for_review: bool
    latest_feedback_at: Optional[datetime]


@dataclass
class FeedbackAggregation:
    """
    Aggregated feedback statistics across all chunks.
    
    Attributes:
        total_feedback_count: Total feedback submissions.
        total_chunks_with_feedback: Number of unique chunks with feedback.
        average_rating: Overall average rating.
        feedback_by_type: Total count by feedback type.
        chunks_flagged_for_review: Number of chunks flagged for review.
        top_problematic_chunks: List of chunk IDs with most negative feedback.
        feedback_by_strategy: Feedback counts grouped by extraction strategy.
        feedback_by_file: Feedback counts grouped by file ID.
    
    Requirements: 27.3, 27.4
    """
    total_feedback_count: int
    total_chunks_with_feedback: int
    average_rating: float
    feedback_by_type: Dict[str, int]
    chunks_flagged_for_review: int
    top_problematic_chunks: List[str]
    feedback_by_strategy: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    feedback_by_file: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class FeedbackStore(Protocol):
    """
    Protocol for feedback storage operations.
    
    Defines the interface for storing and retrieving chunk feedback.
    Implementations can use different storage backends (SQLite, PostgreSQL, etc.).
    
    Requirements: 27.1, 27.2, 27.3, 27.4, 27.5
    """
    
    def save_feedback(self, feedback: FeedbackRecord) -> str:
        """
        Save a feedback record to storage.
        
        Args:
            feedback: FeedbackRecord to save.
        
        Returns:
            The feedback_id of the saved record.
        """
        ...
    
    def get_feedback_for_chunk(
        self,
        chunk_id: str,
        limit: Optional[int] = None
    ) -> List[FeedbackRecord]:
        """
        Get all feedback for a specific chunk.
        
        Args:
            chunk_id: ID of the chunk.
            limit: Optional maximum number of records to return.
        
        Returns:
            List of FeedbackRecord objects.
        """
        ...
    
    def get_feedback_count_for_chunk(self, chunk_id: str) -> int:
        """
        Get the count of feedback for a chunk.
        
        Args:
            chunk_id: ID of the chunk.
        
        Returns:
            Number of feedback records.
        """
        ...
    
    def get_negative_feedback_count(self, chunk_id: str) -> int:
        """
        Get count of negative feedback (rating <= 2) for a chunk.
        
        Args:
            chunk_id: ID of the chunk.
        
        Returns:
            Number of negative feedback records.
        """
        ...
    
    def get_all_feedback(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[FeedbackRecord]:
        """
        Get all feedback records with pagination.
        
        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
        
        Returns:
            List of FeedbackRecord objects.
        """
        ...
    
    def get_aggregated_stats(self) -> Dict[str, Any]:
        """
        Get aggregated feedback statistics.
        
        Returns:
            Dictionary containing aggregated statistics.
        """
        ...


class SQLiteFeedbackStore:
    """
    SQLite implementation of FeedbackStore.
    
    Provides persistent storage for chunk feedback using SQLite database.
    Uses connection pooling via the injected DatabaseConnection.
    
    Attributes:
        db_connection: Injected database connection with connection pooling.
    
    Requirements: 27.1, 27.2, 27.3, 27.4, 27.5
    """
    
    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize the SQLite feedback store.
        
        Args:
            db_connection: Database connection instance with connection pooling.
        
        Raises:
            ChunkViewerError: If db_connection is None.
        """
        if db_connection is None:
            raise ChunkViewerError(
                "Database connection is required",
                details={"parameter": "db_connection"}
            )
        self.db_connection = db_connection
        logger.info("SQLiteFeedbackStore initialized")
    
    def save_feedback(self, feedback: FeedbackRecord) -> str:
        """
        Save a feedback record to the database.
        
        Args:
            feedback: FeedbackRecord to save.
        
        Returns:
            The feedback_id of the saved record.
        
        Raises:
            ChunkViewerError: If save fails.
        """
        try:
            query = """
                INSERT INTO chunk_feedback (
                    chunk_id, feedback_type, rating, comment, user_id, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """
            
            params = (
                feedback.chunk_id,
                feedback.feedback_type,
                feedback.rating,
                feedback.comment,
                feedback.user_id,
                feedback.created_at.isoformat(),
            )
            
            self.db_connection.execute_insert(query, params)
            logger.debug(f"Saved feedback for chunk {feedback.chunk_id}")
            return feedback.feedback_id
            
        except Exception as e:
            logger.error(f"Failed to save feedback: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to save feedback: {e}",
                details={"chunk_id": feedback.chunk_id}
            )
    
    def get_feedback_for_chunk(
        self,
        chunk_id: str,
        limit: Optional[int] = None
    ) -> List[FeedbackRecord]:
        """
        Get all feedback for a specific chunk.
        
        Args:
            chunk_id: ID of the chunk.
            limit: Optional maximum number of records to return.
        
        Returns:
            List of FeedbackRecord objects ordered by created_at descending.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    id, chunk_id, feedback_type, rating, comment, user_id, created_at
                FROM chunk_feedback
                WHERE chunk_id = ?
                ORDER BY created_at DESC
            """
            
            if limit is not None and limit > 0:
                query += f" LIMIT {limit}"
            
            results = self.db_connection.execute_query(query, (chunk_id,))
            
            records: List[FeedbackRecord] = []
            for row in results:
                row_dict = dict(row)
                created_at_str = row_dict.get("created_at", "")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                else:
                    created_at = datetime.now()
                
                records.append(FeedbackRecord(
                    feedback_id=f"fb_{row_dict['id']}",
                    chunk_id=row_dict["chunk_id"],
                    feedback_type=row_dict["feedback_type"],
                    rating=row_dict["rating"],
                    comment=row_dict.get("comment"),
                    user_id=row_dict.get("user_id"),
                    created_at=created_at,
                ))
            
            return records
            
        except Exception as e:
            logger.error(f"Failed to get feedback for chunk: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get feedback for chunk: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def get_feedback_count_for_chunk(self, chunk_id: str) -> int:
        """
        Get the count of feedback for a chunk.
        
        Args:
            chunk_id: ID of the chunk.
        
        Returns:
            Number of feedback records.
        
        Raises:
            ChunkViewerError: If count fails.
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM chunk_feedback
                WHERE chunk_id = ?
            """
            
            results = self.db_connection.execute_query(query, (chunk_id,))
            return results[0]["count"] if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get feedback count: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get feedback count: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def get_negative_feedback_count(self, chunk_id: str) -> int:
        """
        Get count of negative feedback (rating <= 2) for a chunk.
        
        Args:
            chunk_id: ID of the chunk.
        
        Returns:
            Number of negative feedback records.
        
        Raises:
            ChunkViewerError: If count fails.
        """
        try:
            query = """
                SELECT COUNT(*) as count
                FROM chunk_feedback
                WHERE chunk_id = ? AND rating <= 2
            """
            
            results = self.db_connection.execute_query(query, (chunk_id,))
            return results[0]["count"] if results else 0
            
        except Exception as e:
            logger.error(f"Failed to get negative feedback count: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get negative feedback count: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def get_all_feedback(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[FeedbackRecord]:
        """
        Get all feedback records with pagination.
        
        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
        
        Returns:
            List of FeedbackRecord objects.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        try:
            query = """
                SELECT 
                    id, chunk_id, feedback_type, rating, comment, user_id, created_at
                FROM chunk_feedback
                ORDER BY created_at DESC
            """
            
            if limit is not None and limit > 0:
                query += f" LIMIT {limit} OFFSET {offset}"
            
            results = self.db_connection.execute_query(query)
            
            records: List[FeedbackRecord] = []
            for row in results:
                row_dict = dict(row)
                created_at_str = row_dict.get("created_at", "")
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str)
                else:
                    created_at = datetime.now()
                
                records.append(FeedbackRecord(
                    feedback_id=f"fb_{row_dict['id']}",
                    chunk_id=row_dict["chunk_id"],
                    feedback_type=row_dict["feedback_type"],
                    rating=row_dict["rating"],
                    comment=row_dict.get("comment"),
                    user_id=row_dict.get("user_id"),
                    created_at=created_at,
                ))
            
            return records
            
        except Exception as e:
            logger.error(f"Failed to get all feedback: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get all feedback: {e}",
                details={}
            )
    
    def get_aggregated_stats(self) -> Dict[str, Any]:
        """
        Get aggregated feedback statistics.
        
        Returns:
            Dictionary containing aggregated statistics.
        
        Raises:
            ChunkViewerError: If aggregation fails.
        """
        try:
            # Get overall stats
            stats_query = """
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(DISTINCT chunk_id) as unique_chunks,
                    AVG(rating) as avg_rating
                FROM chunk_feedback
            """
            stats_result = self.db_connection.execute_query(stats_query)
            
            # Get counts by feedback type
            type_query = """
                SELECT feedback_type, COUNT(*) as count
                FROM chunk_feedback
                GROUP BY feedback_type
            """
            type_results = self.db_connection.execute_query(type_query)
            
            # Get chunks with multiple negative feedback
            flagged_query = """
                SELECT COUNT(DISTINCT chunk_id) as flagged_count
                FROM chunk_feedback
                WHERE chunk_id IN (
                    SELECT chunk_id
                    FROM chunk_feedback
                    WHERE rating <= 2
                    GROUP BY chunk_id
                    HAVING COUNT(*) >= 2
                )
            """
            flagged_result = self.db_connection.execute_query(flagged_query)
            
            stats = stats_result[0] if stats_result else {}
            
            return {
                "total_feedback_count": stats.get("total_count", 0),
                "total_chunks_with_feedback": stats.get("unique_chunks", 0),
                "average_rating": round(stats.get("avg_rating") or 0, 2),
                "feedback_by_type": {
                    r["feedback_type"]: r["count"] for r in type_results
                },
                "chunks_flagged_for_review": (
                    flagged_result[0]["flagged_count"] if flagged_result else 0
                ),
            }
            
        except Exception as e:
            logger.error(f"Failed to get aggregated stats: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get aggregated stats: {e}",
                details={}
            )


class FeedbackCollector:
    """
    Collects and manages chunk quality feedback.
    
    Provides functionality for submitting feedback, aggregating feedback data,
    generating summaries, and flagging chunks with recurring issues.
    
    Attributes:
        feedback_store: Injected feedback storage implementation.
        negative_threshold: Number of negative reports to flag a chunk (default 2).
    
    Requirements: 27.1, 27.2, 27.3, 27.4, 27.5
    """
    
    # Valid feedback types
    VALID_FEEDBACK_TYPES = {
        FeedbackType.INCORRECT_DATA.value,
        FeedbackType.MISSING_DATA.value,
        FeedbackType.WRONG_BOUNDARIES.value,
        FeedbackType.EXTRACTION_ERROR.value,
        FeedbackType.OTHER.value,
    }
    
    # Default threshold for flagging chunks
    DEFAULT_NEGATIVE_THRESHOLD = 2
    
    def __init__(
        self,
        feedback_store: SQLiteFeedbackStore,
        negative_threshold: int = DEFAULT_NEGATIVE_THRESHOLD
    ) -> None:
        """
        Initialize the feedback collector.
        
        Args:
            feedback_store: Storage implementation for feedback records.
            negative_threshold: Number of negative reports to flag a chunk.
        
        Raises:
            ChunkViewerError: If feedback_store is None.
        """
        if feedback_store is None:
            raise ChunkViewerError(
                "Feedback store is required",
                details={"parameter": "feedback_store"}
            )
        
        self.feedback_store = feedback_store
        self.negative_threshold = max(1, negative_threshold)
        logger.info(
            f"FeedbackCollector initialized with negative_threshold={self.negative_threshold}"
        )
    
    def submit_feedback(
        self,
        chunk_id: str,
        feedback_type: str,
        rating: int,
        comment: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> FeedbackRecord:
        """
        Submit feedback for a chunk.
        
        Validates the feedback data and stores it. If the chunk receives
        multiple negative reports, it will be flagged for review.
        
        Args:
            chunk_id: ID of the chunk to provide feedback for.
            feedback_type: Type of feedback (incorrect_data, missing_data, etc.).
            rating: Quality rating from 1 (poor) to 5 (excellent).
            comment: Optional detailed comment about the issue.
            user_id: Optional user ID for tracking feedback source.
        
        Returns:
            FeedbackRecord representing the submitted feedback.
        
        Raises:
            ChunkViewerError: If validation fails or submission fails.
        
        Requirements: 27.1, 27.2
        """
        # Validate feedback type
        if feedback_type not in self.VALID_FEEDBACK_TYPES:
            raise ChunkViewerError(
                f"Invalid feedback type: {feedback_type}",
                details={
                    "valid_types": list(self.VALID_FEEDBACK_TYPES),
                    "provided": feedback_type
                }
            )
        
        # Validate rating
        if not 1 <= rating <= 5:
            raise ChunkViewerError(
                f"Rating must be between 1 and 5, got {rating}",
                details={"rating": rating}
            )
        
        # Validate chunk_id
        if not chunk_id or not chunk_id.strip():
            raise ChunkViewerError(
                "chunk_id is required",
                details={"chunk_id": chunk_id}
            )
        
        try:
            # Create feedback record
            feedback = FeedbackRecord(
                feedback_id=str(uuid.uuid4()),
                chunk_id=chunk_id.strip(),
                feedback_type=feedback_type,
                rating=rating,
                comment=comment.strip() if comment else None,
                user_id=user_id.strip() if user_id else None,
                created_at=datetime.now(),
            )
            
            # Save to store
            self.feedback_store.save_feedback(feedback)
            
            # Check if chunk should be flagged
            if rating <= 2:
                negative_count = self.feedback_store.get_negative_feedback_count(chunk_id)
                if negative_count >= self.negative_threshold:
                    logger.warning(
                        f"Chunk {chunk_id} flagged for review: "
                        f"{negative_count} negative reports"
                    )
            
            logger.info(
                f"Feedback submitted for chunk {chunk_id}: "
                f"type={feedback_type}, rating={rating}"
            )
            
            return feedback
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to submit feedback: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to submit feedback: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def submit_feedback_from_model(
        self,
        feedback: ChunkFeedback
    ) -> FeedbackRecord:
        """
        Submit feedback using a ChunkFeedback Pydantic model.
        
        Convenience method that accepts the ChunkFeedback model from
        the chunk_visibility models module.
        
        Args:
            feedback: ChunkFeedback Pydantic model.
        
        Returns:
            FeedbackRecord representing the submitted feedback.
        
        Raises:
            ChunkViewerError: If validation fails or submission fails.
        
        Requirements: 27.1, 27.2
        """
        return self.submit_feedback(
            chunk_id=feedback.chunk_id,
            feedback_type=feedback.feedback_type,
            rating=feedback.rating,
            comment=feedback.comment,
            user_id=feedback.user_id,
        )
    
    def get_chunk_feedback_summary(self, chunk_id: str) -> ChunkFeedbackSummary:
        """
        Get a summary of feedback for a specific chunk.
        
        Args:
            chunk_id: ID of the chunk.
        
        Returns:
            ChunkFeedbackSummary with aggregated feedback data.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        try:
            feedback_records = self.feedback_store.get_feedback_for_chunk(chunk_id)
            
            if not feedback_records:
                return ChunkFeedbackSummary(
                    chunk_id=chunk_id,
                    total_feedback_count=0,
                    average_rating=0.0,
                    feedback_by_type={},
                    negative_count=0,
                    flagged_for_review=False,
                    latest_feedback_at=None,
                )
            
            # Calculate statistics
            total_count = len(feedback_records)
            total_rating = sum(f.rating for f in feedback_records)
            average_rating = round(total_rating / total_count, 2)
            
            # Count by type
            feedback_by_type: Dict[str, int] = {}
            for record in feedback_records:
                feedback_by_type[record.feedback_type] = (
                    feedback_by_type.get(record.feedback_type, 0) + 1
                )
            
            # Count negative feedback
            negative_count = sum(1 for f in feedback_records if f.rating <= 2)
            
            # Check if flagged
            flagged_for_review = negative_count >= self.negative_threshold
            
            # Get latest feedback timestamp
            latest_feedback_at = max(f.created_at for f in feedback_records)
            
            return ChunkFeedbackSummary(
                chunk_id=chunk_id,
                total_feedback_count=total_count,
                average_rating=average_rating,
                feedback_by_type=feedback_by_type,
                negative_count=negative_count,
                flagged_for_review=flagged_for_review,
                latest_feedback_at=latest_feedback_at,
            )
            
        except Exception as e:
            logger.error(f"Failed to get chunk feedback summary: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunk feedback summary: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def get_feedback_aggregation(self) -> FeedbackAggregation:
        """
        Get aggregated feedback statistics across all chunks.
        
        Identifies files and extraction strategies with recurring issues.
        
        Returns:
            FeedbackAggregation with overall statistics.
        
        Raises:
            ChunkViewerError: If aggregation fails.
        
        Requirements: 27.3, 27.4
        """
        try:
            stats = self.feedback_store.get_aggregated_stats()
            
            # Get top problematic chunks
            top_problematic = self._get_top_problematic_chunks(limit=10)
            
            return FeedbackAggregation(
                total_feedback_count=stats.get("total_feedback_count", 0),
                total_chunks_with_feedback=stats.get("total_chunks_with_feedback", 0),
                average_rating=stats.get("average_rating", 0.0),
                feedback_by_type=stats.get("feedback_by_type", {}),
                chunks_flagged_for_review=stats.get("chunks_flagged_for_review", 0),
                top_problematic_chunks=top_problematic,
            )
            
        except Exception as e:
            logger.error(f"Failed to get feedback aggregation: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get feedback aggregation: {e}",
                details={}
            )
    
    def get_feedback_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all feedback for the feedback-summary endpoint.
        
        Returns aggregated statistics suitable for API response.
        
        Returns:
            Dictionary containing feedback summary statistics.
        
        Raises:
            ChunkViewerError: If summary generation fails.
        
        Requirements: 27.4
        """
        try:
            aggregation = self.get_feedback_aggregation()
            
            return {
                "total_feedback_count": aggregation.total_feedback_count,
                "total_chunks_with_feedback": aggregation.total_chunks_with_feedback,
                "average_rating": aggregation.average_rating,
                "feedback_by_type": aggregation.feedback_by_type,
                "chunks_flagged_for_review": aggregation.chunks_flagged_for_review,
                "top_problematic_chunks": aggregation.top_problematic_chunks,
                "generated_at": datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"Failed to get feedback summary: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get feedback summary: {e}",
                details={}
            )
    
    def is_chunk_flagged(self, chunk_id: str) -> bool:
        """
        Check if a chunk is flagged for review due to negative feedback.
        
        A chunk is flagged when it has received multiple negative reports
        (rating <= 2) meeting or exceeding the negative_threshold.
        
        Args:
            chunk_id: ID of the chunk to check.
        
        Returns:
            True if chunk is flagged for review, False otherwise.
        
        Raises:
            ChunkViewerError: If check fails.
        
        Requirements: 27.5
        """
        try:
            negative_count = self.feedback_store.get_negative_feedback_count(chunk_id)
            return negative_count >= self.negative_threshold
            
        except Exception as e:
            logger.error(f"Failed to check if chunk is flagged: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to check if chunk is flagged: {e}",
                details={"chunk_id": chunk_id}
            )
    
    def get_flagged_chunks(self) -> List[str]:
        """
        Get all chunk IDs that are flagged for review.
        
        Returns:
            List of chunk IDs with multiple negative reports.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 27.5
        """
        try:
            query = """
                SELECT chunk_id
                FROM chunk_feedback
                WHERE rating <= 2
                GROUP BY chunk_id
                HAVING COUNT(*) >= ?
            """
            
            results = self.feedback_store.db_connection.execute_query(
                query, (self.negative_threshold,)
            )
            
            return [row["chunk_id"] for row in results]
            
        except Exception as e:
            logger.error(f"Failed to get flagged chunks: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get flagged chunks: {e}",
                details={}
            )
    
    def get_feedback_for_chunk(
        self,
        chunk_id: str,
        limit: Optional[int] = None
    ) -> List[FeedbackRecord]:
        """
        Get all feedback records for a specific chunk.
        
        Args:
            chunk_id: ID of the chunk.
            limit: Optional maximum number of records to return.
        
        Returns:
            List of FeedbackRecord objects.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        return self.feedback_store.get_feedback_for_chunk(chunk_id, limit)
    
    def _get_top_problematic_chunks(self, limit: int = 10) -> List[str]:
        """
        Get chunk IDs with the most negative feedback.
        
        Args:
            limit: Maximum number of chunks to return.
        
        Returns:
            List of chunk IDs ordered by negative feedback count descending.
        """
        try:
            query = """
                SELECT chunk_id, COUNT(*) as negative_count
                FROM chunk_feedback
                WHERE rating <= 2
                GROUP BY chunk_id
                ORDER BY negative_count DESC
                LIMIT ?
            """
            
            results = self.feedback_store.db_connection.execute_query(query, (limit,))
            return [row["chunk_id"] for row in results]
            
        except Exception as e:
            logger.warning(f"Failed to get top problematic chunks: {e}")
            return []
