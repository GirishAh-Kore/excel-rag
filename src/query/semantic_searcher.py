"""
Semantic Search Module

Performs semantic search across indexed Excel files using embeddings.
Searches sheets, pivot tables, and charts collections based on query intent.
"""

import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.abstractions.embedding_service import EmbeddingService
from src.indexing.vector_storage import VectorStorageManager
from src.query.query_analyzer import QueryAnalysis

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """A single search result from vector database."""
    
    id: str = Field(..., description="Unique identifier")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score")
    file_id: str = Field(..., description="File ID")
    file_name: str = Field(..., description="File name")
    file_path: str = Field(..., description="File path")
    sheet_name: str = Field(..., description="Sheet name")
    content_type: str = Field(..., description="Content type (sheet, pivot, chart)")
    document: str = Field(..., description="Original embedded text")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "file123:Summary:overview:0",
                "score": 0.92,
                "file_id": "file123",
                "file_name": "Expenses_Jan2024.xlsx",
                "file_path": "/Finance/2024/Expenses_Jan2024.xlsx",
                "sheet_name": "Summary",
                "content_type": "sheet",
                "document": "Summary sheet with monthly expenses...",
                "metadata": {"row_count": 100, "has_numbers": True}
            }
        }


class SearchResults(BaseModel):
    """Collection of search results."""
    
    results: List[SearchResult] = Field(default_factory=list, description="Search results")
    total_results: int = Field(..., ge=0, description="Total number of results")
    query: str = Field(..., description="Original query")
    search_collections: List[str] = Field(
        default_factory=list,
        description="Collections searched"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "results": [],
                "total_results": 5,
                "query": "What were the expenses in January?",
                "search_collections": ["excel_sheets"]
            }
        }


class SemanticSearcher:
    """
    Performs semantic search across indexed Excel files.

    Features:
    - Query embedding generation
    - Multi-collection search (sheets, pivots, charts)
    - Optional BM25 hybrid search with RRF merging
    - Optional cross-encoder reranking
    - Metadata filtering
    - Result ranking and deduplication
    - Comparison mode (returns more files)
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_storage: VectorStorageManager,
        reranker=None,
        hybrid_searcher=None
    ):
        """
        Initialize SemanticSearcher.

        Args:
            embedding_service: Service for generating query embeddings
            vector_storage: Manager for vector database operations
            reranker: Optional ResultReranker for cross-encoder reranking
            hybrid_searcher: Optional HybridSearcher for BM25+semantic fusion
        """
        self.embedding_service = embedding_service
        self.vector_storage = vector_storage
        self.reranker = reranker
        self.hybrid_searcher = hybrid_searcher
        logger.info(
            f"SemanticSearcher initialized with "
            f"embedding={embedding_service.get_model_name()}, "
            f"reranking={'on' if reranker else 'off'}, "
            f"hybrid={'on' if hybrid_searcher else 'off'}"
        )
    
    def search(
        self,
        query: str,
        query_analysis: Optional[QueryAnalysis] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> SearchResults:
        """
        Perform semantic search for a query.
        
        Args:
            query: User query text
            query_analysis: Optional pre-analyzed query
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            SearchResults with ranked candidates
        """
        logger.info(f"Searching for query: {query}")
        
        try:
            # Generate query embedding
            query_embedding = self.embedding_service.embed_text(query)
            logger.debug(f"Generated query embedding with dimension {len(query_embedding)}")
            
            # Determine which collections to search based on query analysis
            collections_to_search = self._determine_collections(query_analysis)
            logger.debug(f"Searching collections: {collections_to_search}")
            
            # Build metadata filters
            search_filters = self._build_filters(query_analysis, filters)
            
            # Search each collection
            all_results = []
            
            if "sheets" in collections_to_search:
                sheet_results = self.vector_storage.search_sheets(
                    query_embedding=query_embedding,
                    top_k=top_k,
                    filters=search_filters
                )
                all_results.extend(self._format_results(sheet_results, "sheet"))
            
            if "pivots" in collections_to_search:
                pivot_results = self.vector_storage.search_pivots(
                    query_embedding=query_embedding,
                    top_k=max(5, top_k // 2),  # Fewer pivot results
                    filters=search_filters
                )
                all_results.extend(self._format_results(pivot_results, "pivot"))
            
            if "charts" in collections_to_search:
                chart_results = self.vector_storage.search_charts(
                    query_embedding=query_embedding,
                    top_k=max(5, top_k // 2),  # Fewer chart results
                    filters=search_filters
                )
                all_results.extend(self._format_results(chart_results, "chart"))
            
            # Sort by score and limit to top_k
            all_results.sort(key=lambda x: x.score, reverse=True)
            all_results = all_results[:top_k]

            # Optional: hybrid search (BM25 + semantic RRF)
            if self.hybrid_searcher and all_results:
                documents = [r.document for r in all_results]
                all_results = self.hybrid_searcher.search(
                    query=query,
                    semantic_results=all_results,
                    documents=documents,
                    top_k=top_k
                )

            # Optional: cross-encoder reranking
            if self.reranker and all_results:
                all_results = self.reranker.rerank(
                    query=query,
                    results=all_results,
                    top_k=top_k
                )

            logger.info(f"Found {len(all_results)} results")
            
            return SearchResults(
                results=all_results,
                total_results=len(all_results),
                query=query,
                search_collections=collections_to_search
            )
            
        except Exception as e:
            logger.error(f"Error during semantic search: {e}", exc_info=True)
            return SearchResults(
                results=[],
                total_results=0,
                query=query,
                search_collections=[]
            )
    
    def search_for_comparison(
        self,
        query: str,
        query_analysis: Optional[QueryAnalysis] = None,
        max_files: int = 5
    ) -> SearchResults:
        """
        Search for files to compare (returns more diverse results).
        
        Args:
            query: User query text
            query_analysis: Optional pre-analyzed query
            max_files: Maximum number of files to return
            
        Returns:
            SearchResults with diverse file candidates
        """
        logger.info(f"Searching for comparison: {query}")
        
        # Search with higher top_k to get more candidates
        results = self.search(
            query=query,
            query_analysis=query_analysis,
            top_k=max_files * 3,  # Get more candidates
            filters=None
        )
        
        # Deduplicate by file and keep top results per file
        file_results = {}
        for result in results.results:
            if result.file_id not in file_results:
                file_results[result.file_id] = result
            elif result.score > file_results[result.file_id].score:
                file_results[result.file_id] = result
        
        # Sort by score and limit to max_files
        diverse_results = sorted(
            file_results.values(),
            key=lambda x: x.score,
            reverse=True
        )[:max_files]
        
        logger.info(f"Found {len(diverse_results)} files for comparison")
        
        return SearchResults(
            results=diverse_results,
            total_results=len(diverse_results),
            query=query,
            search_collections=results.search_collections
        )
    
    def _determine_collections(
        self,
        query_analysis: Optional[QueryAnalysis]
    ) -> List[str]:
        """
        Determine which collections to search based on query analysis.
        
        Args:
            query_analysis: Analyzed query
            
        Returns:
            List of collection names to search
        """
        collections = ["sheets"]  # Always search sheets
        
        if query_analysis:
            data_types = query_analysis.data_types_requested
            
            # Search pivots if pivot-related data types requested
            if "pivots" in data_types:
                collections.append("pivots")
            
            # Search charts if chart-related data types requested
            if "charts" in data_types:
                collections.append("charts")
            
            # If asking about summaries or breakdowns, include pivots
            if query_analysis.intent in ["summarize", "list_items"]:
                if "pivots" not in collections:
                    collections.append("pivots")
        
        return collections
    
    def _build_filters(
        self,
        query_analysis: Optional[QueryAnalysis],
        additional_filters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Build metadata filters for search.
        
        Args:
            query_analysis: Analyzed query
            additional_filters: Additional filters to apply
            
        Returns:
            Combined filters dictionary
        """
        filters = {}
        
        if query_analysis:
            # Add file name filters
            if query_analysis.file_name_hints:
                # Note: This would require the vector store to support
                # partial string matching in metadata
                # For now, we'll skip this and rely on semantic search
                pass
            
            # Add data type filters
            if "numbers" in query_analysis.data_types_requested:
                filters["has_numbers"] = True
            
            if "dates" in query_analysis.data_types_requested:
                filters["has_dates"] = True
            
            # Add pivot/chart filters
            if "pivots" in query_analysis.data_types_requested:
                filters["has_pivot_tables"] = True
            
            if "charts" in query_analysis.data_types_requested:
                filters["has_charts"] = True
        
        # Merge with additional filters
        if additional_filters:
            filters.update(additional_filters)
        
        return filters if filters else None
    
    def _format_results(
        self,
        raw_results: List[Dict[str, Any]],
        content_type: str
    ) -> List[SearchResult]:
        """
        Format raw vector store results into SearchResult objects.
        
        Args:
            raw_results: Raw results from vector store
            content_type: Type of content (sheet, pivot, chart)
            
        Returns:
            List of formatted SearchResult objects
        """
        formatted = []
        
        for result in raw_results:
            try:
                # Extract metadata
                metadata = result.get("metadata", {})
                
                formatted.append(SearchResult(
                    id=result.get("id", ""),
                    score=result.get("score", 0.0),
                    file_id=metadata.get("file_id", ""),
                    file_name=metadata.get("file_name", ""),
                    file_path=metadata.get("file_path", ""),
                    sheet_name=metadata.get("sheet_name", ""),
                    content_type=metadata.get("content_type", content_type),
                    document=result.get("document", ""),
                    metadata=metadata
                ))
            except Exception as e:
                logger.warning(f"Error formatting result: {e}")
                continue
        
        return formatted
    
    def get_file_candidates(
        self,
        search_results: SearchResults
    ) -> List[str]:
        """
        Extract unique file IDs from search results.
        
        Args:
            search_results: Search results
            
        Returns:
            List of unique file IDs
        """
        file_ids = []
        seen = set()
        
        for result in search_results.results:
            if result.file_id not in seen:
                file_ids.append(result.file_id)
                seen.add(result.file_id)
        
        return file_ids
    
    def get_sheet_candidates(
        self,
        search_results: SearchResults,
        file_id: str
    ) -> List[str]:
        """
        Extract unique sheet names for a specific file from search results.
        
        Args:
            search_results: Search results
            file_id: File ID to filter by
            
        Returns:
            List of unique sheet names
        """
        sheet_names = []
        seen = set()
        
        for result in search_results.results:
            if result.file_id == file_id and result.sheet_name not in seen:
                sheet_names.append(result.sheet_name)
                seen.add(result.sheet_name)
        
        return sheet_names
