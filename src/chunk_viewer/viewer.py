"""
Chunk Viewer Service

This module provides the main ChunkViewer service for chunk visibility and
debugging capabilities. It coordinates chunk metadata retrieval, version
management, semantic search, and extraction metadata access.

Key Features:
- View chunks for files and sheets with pagination
- Search chunks with semantic similarity
- Access extraction metadata and quality scores
- Compare extraction strategies side-by-side
- All dependencies injected via constructor (DIP compliant)

Requirements: 1.1, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.6
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.abstractions.embedding_service import EmbeddingService
from src.abstractions.vector_store import VectorStore
from src.chunk_viewer.metadata_store import ChunkMetadataStore
from src.chunk_viewer.version_store import ChunkVersionStore
from src.exceptions import ChunkViewerError
from src.models.chunk_visibility import (
    ChunkFilters,
    ExtractionMetadata,
    PaginatedChunkResponse,
)

logger = logging.getLogger(__name__)


# Configuration constants
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_SEARCH_TOP_K = 100  # Max results from vector search before pagination


@dataclass
class StrategyComparisonResult:
    """
    Result of comparing extraction strategies for a file.
    
    Attributes:
        file_id: ID of the file being compared.
        strategies: List of strategies being compared.
        comparisons: List of comparison details per strategy.
        recommendation: Recommended strategy based on quality scores.
        recommendation_reason: Explanation for the recommendation.
    """
    file_id: str
    strategies: List[str]
    comparisons: List[Dict[str, Any]]
    recommendation: Optional[str]
    recommendation_reason: Optional[str]


@dataclass
class ChunkViewerConfig:
    """
    Configuration for ChunkViewer service.
    
    Attributes:
        default_page_size: Default number of items per page.
        max_page_size: Maximum allowed page size.
        search_top_k: Maximum results from vector search.
        collection_name: Name of the vector store collection.
    """
    default_page_size: int = DEFAULT_PAGE_SIZE
    max_page_size: int = MAX_PAGE_SIZE
    search_top_k: int = DEFAULT_SEARCH_TOP_K
    collection_name: str = "excel_chunks"


class ChunkViewer:
    """
    Provides chunk visibility and debugging capabilities.
    
    Supports viewing, searching, filtering, and comparing chunks
    with full traceability and quality metrics.
    
    All dependencies are injected via constructor following DIP.
    
    Attributes:
        metadata_store: Store for chunk metadata CRUD operations.
        version_store: Store for chunk version management.
        vector_store: Vector database for semantic search.
        embedding_service: Service for generating query embeddings.
        config: Configuration settings for the viewer.
    
    Requirements: 1.1, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.6
    """
    
    def __init__(
        self,
        metadata_store: ChunkMetadataStore,
        version_store: ChunkVersionStore,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        config: Optional[ChunkViewerConfig] = None,
    ) -> None:
        """
        Initialize the ChunkViewer service.
        
        Args:
            metadata_store: Store for chunk metadata operations.
            version_store: Store for chunk version management.
            vector_store: Vector database for semantic search.
            embedding_service: Service for generating embeddings.
            config: Optional configuration settings.
        
        Raises:
            ChunkViewerError: If any required dependency is None.
        """
        if metadata_store is None:
            raise ChunkViewerError(
                "metadata_store is required",
                details={"parameter": "metadata_store"}
            )
        if version_store is None:
            raise ChunkViewerError(
                "version_store is required",
                details={"parameter": "version_store"}
            )
        if vector_store is None:
            raise ChunkViewerError(
                "vector_store is required",
                details={"parameter": "vector_store"}
            )
        if embedding_service is None:
            raise ChunkViewerError(
                "embedding_service is required",
                details={"parameter": "embedding_service"}
            )
        
        self.metadata_store = metadata_store
        self.version_store = version_store
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.config = config or ChunkViewerConfig()
        
        logger.info("ChunkViewer initialized")
    
    def get_chunks_for_file(
        self,
        file_id: str,
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> PaginatedChunkResponse:
        """
        Get all chunks for a file with pagination.
        
        Args:
            file_id: ID of the file to get chunks for.
            page: Page number (1-indexed).
            page_size: Number of items per page (default from config).
        
        Returns:
            PaginatedChunkResponse containing chunks and pagination metadata.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 1.1, 1.5
        """
        if not file_id:
            raise ChunkViewerError(
                "file_id is required",
                details={"parameter": "file_id"}
            )
        
        page_size = self._validate_page_size(page_size)
        page = max(1, page)
        
        try:
            logger.debug(f"Getting chunks for file {file_id}, page {page}")
            
            response = self.metadata_store.get_chunks_for_file(
                file_id=file_id,
                page=page,
                page_size=page_size,
            )
            
            # Enrich chunks with vector store metadata if available
            enriched_chunks = self._enrich_chunks_with_vector_metadata(
                response.chunks
            )
            
            return PaginatedChunkResponse(
                chunks=enriched_chunks,
                total_count=response.total_count,
                page=response.page,
                page_size=response.page_size,
                has_more=response.has_more,
            )
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to get chunks for file: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunks for file: {e}",
                details={"file_id": file_id, "page": page}
            )

    def get_chunks_for_sheet(
        self,
        file_id: str,
        sheet_name: str,
        page: int = 1,
        page_size: Optional[int] = None,
        filters: Optional[ChunkFilters] = None,
    ) -> PaginatedChunkResponse:
        """
        Get chunks for a specific sheet within a file with filtering.
        
        Args:
            file_id: ID of the file containing the sheet.
            sheet_name: Name of the sheet to filter by.
            page: Page number (1-indexed).
            page_size: Number of items per page (default from config).
            filters: Optional additional filters to apply.
        
        Returns:
            PaginatedChunkResponse containing chunks and pagination metadata.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        
        Requirements: 1.4, 2.2, 2.3
        """
        if not file_id:
            raise ChunkViewerError(
                "file_id is required",
                details={"parameter": "file_id"}
            )
        if not sheet_name:
            raise ChunkViewerError(
                "sheet_name is required",
                details={"parameter": "sheet_name"}
            )
        
        page_size = self._validate_page_size(page_size)
        page = max(1, page)
        
        try:
            logger.debug(
                f"Getting chunks for sheet {sheet_name} in file {file_id}"
            )
            
            # Combine sheet filter with any additional filters
            combined_filters = ChunkFilters(
                file_id=file_id,
                sheet_name=sheet_name,
                extraction_strategy=(
                    filters.extraction_strategy if filters else None
                ),
                content_type=filters.content_type if filters else None,
                min_quality_score=(
                    filters.min_quality_score if filters else None
                ),
            )
            
            response = self.metadata_store.get_chunks_with_filters(
                filters=combined_filters,
                page=page,
                page_size=page_size,
            )
            
            # Enrich chunks with vector store metadata
            enriched_chunks = self._enrich_chunks_with_vector_metadata(
                response.chunks
            )
            
            return PaginatedChunkResponse(
                chunks=enriched_chunks,
                total_count=response.total_count,
                page=response.page,
                page_size=response.page_size,
                has_more=response.has_more,
            )
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to get chunks for sheet: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunks for sheet: {e}",
                details={"file_id": file_id, "sheet_name": sheet_name}
            )
    
    def search_chunks(
        self,
        query: str,
        filters: Optional[ChunkFilters] = None,
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> PaginatedChunkResponse:
        """
        Search chunks with semantic similarity and optional filters.
        
        Performs semantic search using embeddings and combines results
        with metadata filtering. Returns chunks ordered by similarity score.
        
        Args:
            query: Search query text for semantic matching.
            filters: Optional filters to apply (combined with AND logic).
            page: Page number (1-indexed).
            page_size: Number of items per page (default from config).
        
        Returns:
            PaginatedChunkResponse with chunks including similarity_score.
        
        Raises:
            ChunkViewerError: If search fails or query is empty.
        
        Requirements: 2.1, 2.2, 2.3, 2.4
        """
        if not query or not query.strip():
            raise ChunkViewerError(
                "Search query is required",
                details={"parameter": "query"}
            )
        
        page_size = self._validate_page_size(page_size)
        page = max(1, page)
        
        try:
            logger.debug(f"Searching chunks with query: {query[:50]}...")
            
            # Generate query embedding
            query_embedding = self.embedding_service.embed_text(query.strip())
            
            # Build vector store filters from ChunkFilters
            vector_filters = self._build_vector_filters(filters)
            
            # Search vector store
            search_results = self.vector_store.search(
                collection=self.config.collection_name,
                query_embedding=query_embedding,
                top_k=self.config.search_top_k,
                filters=vector_filters,
            )
            
            if not search_results:
                logger.debug("No chunks found matching search query")
                return PaginatedChunkResponse(
                    chunks=[],
                    total_count=0,
                    page=page,
                    page_size=page_size,
                    has_more=False,
                )
            
            # Apply pagination to search results
            total_count = len(search_results)
            offset = (page - 1) * page_size
            paginated_results = search_results[offset:offset + page_size]
            
            # Enrich results with metadata from database
            enriched_chunks = self._enrich_search_results(paginated_results)
            
            has_more = (offset + len(paginated_results)) < total_count
            
            return PaginatedChunkResponse(
                chunks=enriched_chunks,
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_more=has_more,
            )
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to search chunks: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to search chunks: {e}",
                details={"query": query[:100], "filters": filters}
            )
    
    def get_extraction_metadata(self, file_id: str) -> ExtractionMetadata:
        """
        Get extraction metadata for a file.
        
        Returns details about the extraction process including strategy used,
        quality scores, errors, and warnings.
        
        Args:
            file_id: ID of the file to get extraction metadata for.
        
        Returns:
            ExtractionMetadata object with extraction details.
        
        Raises:
            ChunkViewerError: If file not found or retrieval fails.
        
        Requirements: 3.1
        """
        if not file_id:
            raise ChunkViewerError(
                "file_id is required",
                details={"parameter": "file_id"}
            )
        
        try:
            logger.debug(f"Getting extraction metadata for file {file_id}")
            
            metadata = self.metadata_store.get_extraction_metadata(file_id)
            
            if metadata is None:
                raise ChunkViewerError(
                    f"Extraction metadata not found for file {file_id}",
                    details={"file_id": file_id}
                )
            
            return metadata
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to get extraction metadata: {e}", exc_info=True
            )
            raise ChunkViewerError(
                f"Failed to get extraction metadata: {e}",
                details={"file_id": file_id}
            )

    def compare_extraction_strategies(
        self,
        file_id: str,
        strategies: List[str],
    ) -> StrategyComparisonResult:
        """
        Compare the same file processed with different extraction strategies.
        
        Provides side-by-side comparison of extraction results including
        quality scores, chunk counts, and recommendations.
        
        Args:
            file_id: ID of the file to compare strategies for.
            strategies: List of strategy names to compare.
        
        Returns:
            StrategyComparisonResult with comparison details and recommendation.
        
        Raises:
            ChunkViewerError: If comparison fails or strategies are invalid.
        
        Requirements: 3.6
        """
        if not file_id:
            raise ChunkViewerError(
                "file_id is required",
                details={"parameter": "file_id"}
            )
        if not strategies or len(strategies) < 2:
            raise ChunkViewerError(
                "At least two strategies are required for comparison",
                details={"strategies": strategies}
            )
        
        try:
            logger.debug(
                f"Comparing strategies {strategies} for file {file_id}"
            )
            
            comparisons: List[Dict[str, Any]] = []
            best_strategy: Optional[str] = None
            best_score: float = -1.0
            
            for strategy in strategies:
                comparison = self._get_strategy_comparison_data(
                    file_id, strategy
                )
                comparisons.append(comparison)
                
                # Track best strategy by quality score
                quality_score = comparison.get("quality_score", 0.0)
                if quality_score > best_score:
                    best_score = quality_score
                    best_strategy = strategy
            
            # Generate recommendation reason
            recommendation_reason = self._generate_recommendation_reason(
                comparisons, best_strategy
            )
            
            return StrategyComparisonResult(
                file_id=file_id,
                strategies=strategies,
                comparisons=comparisons,
                recommendation=best_strategy,
                recommendation_reason=recommendation_reason,
            )
            
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(
                f"Failed to compare extraction strategies: {e}", exc_info=True
            )
            raise ChunkViewerError(
                f"Failed to compare extraction strategies: {e}",
                details={"file_id": file_id, "strategies": strategies}
            )
    
    def get_chunk_versions(
        self,
        file_id: str,
        chunk_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get version history for chunks in a file.
        
        Args:
            file_id: ID of the file to get versions for.
            chunk_id: Optional specific chunk ID to get versions for.
        
        Returns:
            List of version records with metadata.
        
        Raises:
            ChunkViewerError: If retrieval fails.
        """
        if not file_id:
            raise ChunkViewerError(
                "file_id is required",
                details={"parameter": "file_id"}
            )
        
        try:
            if chunk_id:
                # Get versions for specific chunk
                versions = self.version_store.get_version_history(chunk_id)
                return [
                    {
                        "version_id": v.version_id,
                        "chunk_id": v.chunk_id,
                        "version_number": v.version_number,
                        "chunk_text": v.chunk_text,
                        "extraction_strategy": v.extraction_strategy,
                        "indexed_at": v.indexed_at.isoformat(),
                        "change_summary": v.change_summary,
                    }
                    for v in versions
                ]
            else:
                # Get all versions for file
                return self.version_store.get_versions_for_file(file_id)
                
        except ChunkViewerError:
            raise
        except Exception as e:
            logger.error(f"Failed to get chunk versions: {e}", exc_info=True)
            raise ChunkViewerError(
                f"Failed to get chunk versions: {e}",
                details={"file_id": file_id, "chunk_id": chunk_id}
            )
    
    def _validate_page_size(self, page_size: Optional[int]) -> int:
        """
        Validate and normalize page size.
        
        Args:
            page_size: Requested page size or None for default.
        
        Returns:
            Validated page size within allowed bounds.
        """
        if page_size is None:
            return self.config.default_page_size
        return min(max(1, page_size), self.config.max_page_size)
    
    def _build_vector_filters(
        self,
        filters: Optional[ChunkFilters],
    ) -> Optional[Dict[str, Any]]:
        """
        Build vector store filters from ChunkFilters.
        
        Args:
            filters: ChunkFilters object or None.
        
        Returns:
            Dictionary of filters for vector store or None.
        """
        if filters is None or filters.is_empty():
            return None
        
        vector_filters: Dict[str, Any] = {}
        
        if filters.file_id is not None:
            vector_filters["file_id"] = filters.file_id
        
        if filters.sheet_name is not None:
            vector_filters["sheet_name"] = filters.sheet_name
        
        if filters.extraction_strategy is not None:
            vector_filters["extraction_strategy"] = filters.extraction_strategy
        
        if filters.content_type is not None:
            vector_filters["content_type"] = filters.content_type
        
        return vector_filters if vector_filters else None
    
    def _enrich_chunks_with_vector_metadata(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Enrich chunk data with metadata from vector store.
        
        Adds embedding dimensions, token count, and model info.
        
        Args:
            chunks: List of chunk dictionaries from metadata store.
        
        Returns:
            Enriched chunk dictionaries.
        """
        if not chunks:
            return chunks
        
        # Get embedding model info
        embedding_model = self.embedding_service.get_model_name()
        embedding_dimensions = self.embedding_service.get_embedding_dimension()
        
        enriched = []
        for chunk in chunks:
            enriched_chunk = dict(chunk)
            enriched_chunk["embedding_model"] = embedding_model
            enriched_chunk["embedding_dimensions"] = embedding_dimensions
            
            # Estimate token count from chunk text
            chunk_text = chunk.get("chunk_text", "")
            enriched_chunk["token_count"] = self._estimate_token_count(
                chunk_text
            )
            
            enriched.append(enriched_chunk)
        
        return enriched

    def _enrich_search_results(
        self,
        search_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Enrich vector search results with database metadata.
        
        Combines vector store results with chunk metadata from database.
        
        Args:
            search_results: Results from vector store search.
        
        Returns:
            Enriched chunk dictionaries with similarity scores.
        """
        if not search_results:
            return []
        
        enriched = []
        embedding_model = self.embedding_service.get_model_name()
        embedding_dimensions = self.embedding_service.get_embedding_dimension()
        
        for result in search_results:
            chunk_id = result.get("id")
            
            # Get additional metadata from database
            db_metadata = self.metadata_store.get_chunk(chunk_id)
            
            enriched_chunk: Dict[str, Any] = {
                "chunk_id": chunk_id,
                "chunk_text": result.get("document", ""),
                "similarity_score": result.get("score", 0.0),
                "embedding_model": embedding_model,
                "embedding_dimensions": embedding_dimensions,
            }
            
            # Merge vector store metadata
            if result.get("metadata"):
                enriched_chunk.update(result["metadata"])
            
            # Merge database metadata
            if db_metadata:
                enriched_chunk["file_id"] = db_metadata.get("file_id")
                enriched_chunk["file_name"] = db_metadata.get("file_name")
                enriched_chunk["start_row"] = db_metadata.get("start_row")
                enriched_chunk["end_row"] = db_metadata.get("end_row")
                enriched_chunk["extraction_strategy"] = db_metadata.get(
                    "extraction_strategy"
                )
                enriched_chunk["raw_source_data"] = db_metadata.get(
                    "raw_source_data"
                )
                enriched_chunk["indexed_at"] = db_metadata.get("indexed_at")
            
            # Estimate token count
            enriched_chunk["token_count"] = self._estimate_token_count(
                enriched_chunk.get("chunk_text", "")
            )
            
            enriched.append(enriched_chunk)
        
        return enriched
    
    def _get_strategy_comparison_data(
        self,
        file_id: str,
        strategy: str,
    ) -> Dict[str, Any]:
        """
        Get comparison data for a specific extraction strategy.
        
        Args:
            file_id: ID of the file.
            strategy: Extraction strategy name.
        
        Returns:
            Dictionary with strategy comparison metrics.
        """
        # Get chunks for this strategy
        filters = ChunkFilters(
            file_id=file_id,
            extraction_strategy=strategy,
        )
        
        chunks_response = self.metadata_store.get_chunks_with_filters(
            filters=filters,
            page=1,
            page_size=1,  # Just need count
        )
        
        # Try to get extraction metadata
        extraction_metadata: Optional[ExtractionMetadata] = None
        try:
            extraction_metadata = self.metadata_store.get_extraction_metadata(
                file_id
            )
        except Exception:
            pass
        
        comparison: Dict[str, Any] = {
            "strategy": strategy,
            "chunk_count": chunks_response.total_count,
            "quality_score": 0.0,
            "has_headers": False,
            "has_data": False,
            "data_completeness": 0.0,
            "structure_clarity": 0.0,
            "error_count": 0,
            "warning_count": 0,
        }
        
        # Add extraction metadata if available and matches strategy
        if (
            extraction_metadata
            and extraction_metadata.strategy_used == strategy
        ):
            comparison["quality_score"] = extraction_metadata.quality_score
            comparison["has_headers"] = extraction_metadata.has_headers
            comparison["has_data"] = extraction_metadata.has_data
            comparison["data_completeness"] = (
                extraction_metadata.data_completeness
            )
            comparison["structure_clarity"] = (
                extraction_metadata.structure_clarity
            )
            comparison["error_count"] = len(
                extraction_metadata.extraction_errors
            )
            comparison["warning_count"] = len(
                extraction_metadata.extraction_warnings
            )
            comparison["extraction_duration_ms"] = (
                extraction_metadata.extraction_duration_ms
            )
        
        return comparison
    
    def _generate_recommendation_reason(
        self,
        comparisons: List[Dict[str, Any]],
        best_strategy: Optional[str],
    ) -> Optional[str]:
        """
        Generate explanation for strategy recommendation.
        
        Args:
            comparisons: List of strategy comparison data.
            best_strategy: The recommended strategy name.
        
        Returns:
            Human-readable recommendation reason.
        """
        if not best_strategy or not comparisons:
            return None
        
        best_comparison = next(
            (c for c in comparisons if c["strategy"] == best_strategy),
            None
        )
        
        if not best_comparison:
            return None
        
        reasons = []
        
        quality_score = best_comparison.get("quality_score", 0.0)
        if quality_score >= 0.8:
            reasons.append(f"highest quality score ({quality_score:.2f})")
        elif quality_score >= 0.5:
            reasons.append(f"good quality score ({quality_score:.2f})")
        
        if best_comparison.get("has_headers"):
            reasons.append("detected headers")
        
        if best_comparison.get("has_data"):
            reasons.append("contains data")
        
        completeness = best_comparison.get("data_completeness", 0.0)
        if completeness >= 0.9:
            reasons.append(f"excellent data completeness ({completeness:.0%})")
        
        error_count = best_comparison.get("error_count", 0)
        if error_count == 0:
            reasons.append("no extraction errors")
        
        if not reasons:
            return f"Best overall performance among compared strategies"
        
        return f"Recommended due to: {', '.join(reasons)}"
    
    def _estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Uses a simple heuristic of ~4 characters per token.
        
        Args:
            text: Text to estimate tokens for.
        
        Returns:
            Estimated token count.
        """
        if not text:
            return 0
        # Rough estimate: ~4 characters per token for English text
        return max(1, len(text) // 4)
