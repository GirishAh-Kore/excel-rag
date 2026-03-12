"""
Sheet Selector Module

Selects the most relevant sheet(s) within an Excel file based on query intent.
Uses multiple scoring factors including sheet name similarity, header matching,
data type alignment, and content similarity.
"""

import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from pydantic import BaseModel, Field
from fuzzywuzzy import fuzz

from src.models.domain_models import SheetData, SheetSelection
from src.indexing.metadata_storage import MetadataStorageManager
from src.query.query_analyzer import QueryAnalysis
from src.query.semantic_searcher import SearchResults
from src.text_processing.preprocessor import TextPreprocessor

logger = logging.getLogger(__name__)


class ScoredSheet(BaseModel):
    """A sheet with relevance scores."""
    
    sheet_data: SheetData = Field(..., description="Sheet data")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Overall relevance score")
    name_score: float = Field(..., ge=0.0, le=1.0, description="Sheet name similarity score")
    header_score: float = Field(..., ge=0.0, le=1.0, description="Header/column match score")
    data_type_score: float = Field(..., ge=0.0, le=1.0, description="Data type alignment score")
    content_score: float = Field(..., ge=0.0, le=1.0, description="Content sample similarity score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sheet_data": {},
                "relevance_score": 0.85,
                "name_score": 0.90,
                "header_score": 0.85,
                "data_type_score": 0.80,
                "content_score": 0.85
            }
        }


class MultiSheetSelection(BaseModel):
    """Result of multi-sheet selection."""
    
    selected_sheets: List[ScoredSheet] = Field(
        default_factory=list,
        description="Selected sheets"
    )
    combination_strategy: str = Field(
        ...,
        description="How to combine data (union, join, separate)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "selected_sheets": [],
                "combination_strategy": "union"
            }
        }


class SheetSelector:
    """
    Selects relevant sheet(s) within an Excel file.
    
    Scoring algorithm:
    - Sheet name similarity: 30% weight (fuzzy matching)
    - Header/column match: 40% weight (keyword matching)
    - Data type alignment: 20% weight (based on query intent)
    - Content sample similarity: 10% weight (from embeddings)
    
    Features:
    - Single sheet selection (highest score > 70%)
    - Multi-sheet selection (multiple sheets > 70%)
    - Parallel processing for efficiency
    - Support for different combination strategies
    """
    
    # Scoring weights
    NAME_WEIGHT = 0.3
    HEADER_WEIGHT = 0.4
    DATA_TYPE_WEIGHT = 0.2
    CONTENT_WEIGHT = 0.1
    
    # Selection threshold
    SELECTION_THRESHOLD = 0.7
    
    # Max workers for parallel processing
    MAX_WORKERS = 5
    
    def __init__(
        self,
        metadata_storage: MetadataStorageManager,
        text_preprocessor: Optional[TextPreprocessor] = None
    ):
        """
        Initialize SheetSelector.
        
        Args:
            metadata_storage: Manager for metadata storage
            text_preprocessor: Optional text preprocessor for keyword extraction
        """
        self.metadata_storage = metadata_storage
        self.text_preprocessor = text_preprocessor
        logger.info("SheetSelector initialized")
    
    def select_sheet(
        self,
        file_id: str,
        query: str,
        query_analysis: Optional[QueryAnalysis] = None,
        search_results: Optional[SearchResults] = None
    ) -> SheetSelection:
        """
        Select most relevant sheet for query.
        
        Args:
            file_id: File ID
            query: User query
            query_analysis: Optional pre-analyzed query
            search_results: Optional search results for content scoring
            
        Returns:
            SheetSelection with selected sheet
        """
        logger.info(f"Selecting sheet for file: {file_id}")
        
        # Get all sheets for this file
        sheets_metadata = self.metadata_storage.get_sheet_metadata(file_id)
        
        if not sheets_metadata:
            logger.warning(f"No sheets found for file: {file_id}")
            return SheetSelection(
                sheet_name="",
                relevance_score=0.0,
                requires_clarification=True
            )
        
        # Score each sheet
        scored_sheets = []
        
        for sheet_meta in sheets_metadata:
            # Convert to SheetData (simplified - in real use, load full data)
            sheet_data = self._metadata_to_sheet_data(sheet_meta)
            
            # Calculate scores
            scored_sheet = self._score_sheet(
                sheet_data,
                query,
                query_analysis,
                search_results
            )
            
            scored_sheets.append(scored_sheet)
        
        # Sort by relevance score
        scored_sheets.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Select top sheet
        top_sheet = scored_sheets[0]
        
        logger.info(
            f"Selected sheet: {top_sheet.sheet_data.sheet_name} "
            f"(score: {top_sheet.relevance_score:.3f})"
        )
        
        # Check if clarification is needed
        requires_clarification = top_sheet.relevance_score < self.SELECTION_THRESHOLD
        
        return SheetSelection(
            sheet_name=top_sheet.sheet_data.sheet_name,
            relevance_score=top_sheet.relevance_score,
            requires_clarification=requires_clarification
        )
    
    def select_multiple_sheets(
        self,
        file_id: str,
        query: str,
        query_analysis: Optional[QueryAnalysis] = None,
        search_results: Optional[SearchResults] = None
    ) -> MultiSheetSelection:
        """
        Select multiple relevant sheets (parallel processing).
        
        Args:
            file_id: File ID
            query: User query
            query_analysis: Optional pre-analyzed query
            search_results: Optional search results
            
        Returns:
            MultiSheetSelection with selected sheets and combination strategy
        """
        logger.info(f"Selecting multiple sheets for file: {file_id}")
        
        # Get all sheets for this file
        sheets_metadata = self.metadata_storage.get_sheet_metadata(file_id)
        
        if not sheets_metadata:
            logger.warning(f"No sheets found for file: {file_id}")
            return MultiSheetSelection(
                selected_sheets=[],
                combination_strategy="none"
            )
        
        # Score sheets in parallel
        scored_sheets = []
        
        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            # Submit scoring tasks
            future_to_sheet = {}
            
            for sheet_meta in sheets_metadata:
                sheet_data = self._metadata_to_sheet_data(sheet_meta)
                
                future = executor.submit(
                    self._score_sheet,
                    sheet_data,
                    query,
                    query_analysis,
                    search_results
                )
                
                future_to_sheet[future] = sheet_data
            
            # Collect results
            for future in as_completed(future_to_sheet):
                try:
                    scored_sheet = future.result()
                    scored_sheets.append(scored_sheet)
                except Exception as e:
                    sheet_data = future_to_sheet[future]
                    logger.error(
                        f"Error scoring sheet {sheet_data.sheet_name}: {e}",
                        exc_info=True
                    )
        
        # Filter sheets above threshold
        selected_sheets = [
            sheet for sheet in scored_sheets
            if sheet.relevance_score >= self.SELECTION_THRESHOLD
        ]
        
        # Sort by relevance
        selected_sheets.sort(key=lambda x: x.relevance_score, reverse=True)
        
        # Determine combination strategy
        combination_strategy = self._determine_combination_strategy(
            selected_sheets,
            query_analysis
        )
        
        logger.info(
            f"Selected {len(selected_sheets)} sheets "
            f"(strategy: {combination_strategy})"
        )
        
        return MultiSheetSelection(
            selected_sheets=selected_sheets,
            combination_strategy=combination_strategy
        )
    
    def _score_sheet(
        self,
        sheet_data: SheetData,
        query: str,
        query_analysis: Optional[QueryAnalysis],
        search_results: Optional[SearchResults]
    ) -> ScoredSheet:
        """
        Calculate relevance score for a sheet.
        
        Args:
            sheet_data: Sheet data
            query: User query
            query_analysis: Optional query analysis
            search_results: Optional search results
            
        Returns:
            ScoredSheet with all scores
        """
        # Calculate individual scores
        name_score = self._calculate_name_score(sheet_data.sheet_name, query)
        
        header_score = self._calculate_header_score(
            sheet_data.headers,
            query,
            query_analysis
        )
        
        data_type_score = self._calculate_data_type_score(
            sheet_data,
            query_analysis
        )
        
        content_score = self._calculate_content_score(
            sheet_data,
            search_results
        )
        
        # Calculate overall relevance score
        relevance_score = (
            name_score * self.NAME_WEIGHT +
            header_score * self.HEADER_WEIGHT +
            data_type_score * self.DATA_TYPE_WEIGHT +
            content_score * self.CONTENT_WEIGHT
        )
        
        return ScoredSheet(
            sheet_data=sheet_data,
            relevance_score=relevance_score,
            name_score=name_score,
            header_score=header_score,
            data_type_score=data_type_score,
            content_score=content_score
        )
    
    def _calculate_name_score(self, sheet_name: str, query: str) -> float:
        """
        Calculate sheet name similarity using fuzzy matching.
        
        Args:
            sheet_name: Sheet name
            query: User query
            
        Returns:
            Name similarity score (0-1)
        """
        # Use fuzzywuzzy for fuzzy string matching
        query_lower = query.lower()
        sheet_name_lower = sheet_name.lower()
        
        # Partial ratio (checks if sheet name is substring of query or vice versa)
        partial_score = fuzz.partial_ratio(sheet_name_lower, query_lower) / 100.0
        
        # Token sort ratio (handles word order differences)
        token_score = fuzz.token_sort_ratio(sheet_name_lower, query_lower) / 100.0
        
        # Use the higher score
        score = max(partial_score, token_score)
        
        # Boost score if exact word match
        query_words = set(query_lower.split())
        sheet_words = set(sheet_name_lower.split())
        
        if query_words & sheet_words:  # Intersection
            score = min(1.0, score + 0.2)
        
        return score
    
    def _calculate_header_score(
        self,
        headers: List[str],
        query: str,
        query_analysis: Optional[QueryAnalysis]
    ) -> float:
        """
        Calculate header/column match score using keyword matching.
        
        Args:
            headers: Column headers
            query: User query
            query_analysis: Optional query analysis
            
        Returns:
            Header match score (0-1)
        """
        if not headers:
            return 0.0
        
        # Extract keywords from query
        if self.text_preprocessor:
            query_keywords = self.text_preprocessor.extract_keywords(query)
        else:
            # Fallback: simple word extraction
            query_keywords = [
                word.lower() for word in query.split()
                if len(word) > 3
            ]
        
        # Add entities from query analysis
        if query_analysis:
            query_keywords.extend([e.lower() for e in query_analysis.entities])
        
        # Remove duplicates
        query_keywords = list(set(query_keywords))
        
        if not query_keywords:
            return 0.0
        
        # Check how many keywords match headers
        matches = 0
        
        for keyword in query_keywords:
            for header in headers:
                header_lower = header.lower()
                
                # Exact match
                if keyword in header_lower or header_lower in keyword:
                    matches += 1
                    break
                
                # Fuzzy match
                if fuzz.partial_ratio(keyword, header_lower) > 80:
                    matches += 0.5
                    break
        
        # Normalize score
        score = matches / len(query_keywords) if query_keywords else 0.0
        
        return min(1.0, score)
    
    def _calculate_data_type_score(
        self,
        sheet_data: SheetData,
        query_analysis: Optional[QueryAnalysis]
    ) -> float:
        """
        Calculate data type alignment score based on query intent.
        
        Args:
            sheet_data: Sheet data
            query_analysis: Optional query analysis
            
        Returns:
            Data type alignment score (0-1)
        """
        if not query_analysis:
            return 0.5  # Neutral score if no analysis
        
        score = 0.0
        factors = 0
        
        # Check for requested data types
        data_types_requested = query_analysis.data_types_requested
        
        if "numbers" in data_types_requested:
            if sheet_data.has_numbers:
                score += 1.0
            factors += 1
        
        if "dates" in data_types_requested:
            if sheet_data.has_dates:
                score += 1.0
            factors += 1
        
        if "pivots" in data_types_requested:
            if sheet_data.has_pivot_tables:
                score += 1.0
            factors += 1
        
        if "charts" in data_types_requested:
            if sheet_data.has_charts:
                score += 1.0
            factors += 1
        
        # Normalize
        if factors > 0:
            score = score / factors
        else:
            score = 0.5  # Neutral if no specific data types requested
        
        return score
    
    def _calculate_content_score(
        self,
        sheet_data: SheetData,
        search_results: Optional[SearchResults]
    ) -> float:
        """
        Calculate content sample similarity from search results.
        
        Args:
            sheet_data: Sheet data
            search_results: Optional search results
            
        Returns:
            Content similarity score (0-1)
        """
        if not search_results:
            return 0.5  # Neutral score if no search results
        
        # Find this sheet in search results
        max_score = 0.0
        
        for result in search_results.results:
            if result.sheet_name == sheet_data.sheet_name:
                max_score = max(max_score, result.score)
        
        return max_score
    
    def _determine_combination_strategy(
        self,
        selected_sheets: List[ScoredSheet],
        query_analysis: Optional[QueryAnalysis]
    ) -> str:
        """
        Determine how to combine data from multiple sheets.
        
        Args:
            selected_sheets: Selected sheets
            query_analysis: Optional query analysis
            
        Returns:
            Combination strategy ("union", "join", "separate", "none")
        """
        if len(selected_sheets) == 0:
            return "none"
        
        if len(selected_sheets) == 1:
            return "separate"
        
        # Check if sheets have similar structure (same headers)
        if len(selected_sheets) >= 2:
            first_headers = set(selected_sheets[0].sheet_data.headers)
            
            similar_structure = all(
                len(first_headers & set(sheet.sheet_data.headers)) / len(first_headers) > 0.7
                for sheet in selected_sheets[1:]
            )
            
            if similar_structure:
                # If comparison query, keep separate
                if query_analysis and query_analysis.is_comparison:
                    return "separate"
                else:
                    return "union"
            else:
                return "separate"
        
        return "separate"
    
    def _metadata_to_sheet_data(self, sheet_meta: Dict[str, Any]) -> SheetData:
        """
        Convert sheet metadata dictionary to SheetData object.
        
        Args:
            sheet_meta: Sheet metadata dictionary
            
        Returns:
            SheetData object
        """
        import json
        from src.models.domain_models import DataType
        
        # Parse JSON fields
        headers = json.loads(sheet_meta.get("headers", "[]"))
        data_types_dict = json.loads(sheet_meta.get("data_types", "{}"))
        
        # Convert data types
        data_types = {
            k: DataType(v) for k, v in data_types_dict.items()
        }
        
        return SheetData(
            sheet_name=sheet_meta["sheet_name"],
            headers=headers,
            rows=[],  # Not loading full rows for selection
            data_types=data_types,
            row_count=sheet_meta.get("row_count", 0),
            column_count=sheet_meta.get("column_count", 0),
            summary="",  # Will be loaded separately if needed
            has_dates=False,  # Would need to check data_types
            has_numbers=False,  # Would need to check data_types
            pivot_tables=[],
            charts=[],
            has_pivot_tables=sheet_meta.get("has_pivot_tables", False),
            has_charts=sheet_meta.get("has_charts", False)
        )
