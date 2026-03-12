"""
Chunk Viewer Module

This module provides chunk visibility and debugging capabilities for the
Excel RAG system. It allows developers to inspect chunks generated during
indexing, understand extraction strategies, and debug retrieval issues.

Key Components:
- ChunkMetadataStore: CRUD operations for chunk metadata with filtering
- ChunkVersionStore: Version tracking for re-indexing changes
- ChunkViewer: Main service for chunk visibility operations
- FeedbackCollector: User feedback collection on chunk quality

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 3.1, 3.5, 3.6,
              21.1, 21.2, 21.3, 21.4, 21.5, 27.1, 27.2, 27.3, 27.4, 27.5
"""

from src.chunk_viewer.feedback import (
    ChunkFeedbackSummary,
    FeedbackAggregation,
    FeedbackCollector,
    FeedbackRecord,
    FeedbackType,
    SQLiteFeedbackStore,
)
from src.chunk_viewer.metadata_store import ChunkMetadataStore
from src.chunk_viewer.version_store import ChunkVersionStore, VersionDiff
from src.chunk_viewer.viewer import (
    ChunkViewer,
    ChunkViewerConfig,
    StrategyComparisonResult,
)

__all__ = [
    # Metadata Store
    "ChunkMetadataStore",
    # Version Store
    "ChunkVersionStore",
    "VersionDiff",
    # Viewer
    "ChunkViewer",
    "ChunkViewerConfig",
    "StrategyComparisonResult",
    # Feedback
    "FeedbackCollector",
    "FeedbackRecord",
    "FeedbackType",
    "FeedbackAggregation",
    "ChunkFeedbackSummary",
    "SQLiteFeedbackStore",
]
