"""
File Selector Module

Ranks and selects files based on semantic similarity, metadata matching,
and user preferences. Handles file disambiguation when multiple candidates exist.
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from src.models.domain_models import FileMetadata, RankedFile
from src.query.semantic_searcher import SearchResults
from src.indexing.metadata_storage import MetadataStorageManager
from src.query.date_parser import DateParser
from src.query.preference_manager import PreferenceManager

logger = logging.getLogger(__name__)


class FileSelection(BaseModel):
    """Result of file selection process."""
    
    selected_file: Optional[RankedFile] = Field(
        default=None,
        description="Selected file if confidence is high enough"
    )
    candidates: List[RankedFile] = Field(
        default_factory=list,
        description="Top candidate files for user selection"
    )
    requires_clarification: bool = Field(
        default=False,
        description="Whether user clarification is needed"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence in selection"
    )
    allow_none_option: bool = Field(
        default=True,
        description="Whether to allow 'none of these' option"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "selected_file": None,
                "candidates": [],
                "requires_clarification": True,
                "confidence": 0.75,
                "allow_none_option": True
            }
        }


class FileSelector:
    """
    Ranks and selects files based on multiple scoring factors.
    
    Scoring algorithm:
    - Semantic similarity: 50% weight (from vector search)
    - Metadata match: 30% weight (dates, paths, recency)
    - User preference: 20% weight (historical selections)
    
    Features:
    - Automatic selection when confidence > 90%
    - Clarification request when confidence < 90%
    - Date parsing from file names
    - User preference learning
    """
    
    # Scoring weights
    SEMANTIC_WEIGHT = 0.5
    METADATA_WEIGHT = 0.3
    PREFERENCE_WEIGHT = 0.2
    
    # Selection threshold
    AUTO_SELECT_THRESHOLD = 0.9
    
    def __init__(
        self,
        metadata_storage: MetadataStorageManager,
        date_parser: DateParser,
        preference_manager: PreferenceManager
    ):
        """
        Initialize FileSelector.
        
        Args:
            metadata_storage: Manager for metadata storage
            date_parser: Parser for extracting dates from file names
            preference_manager: Manager for user preferences
        """
        self.metadata_storage = metadata_storage
        self.date_parser = date_parser
        self.preference_manager = preference_manager
        logger.info("FileSelector initialized")
    
    def rank_files(
        self,
        query: str,
        search_results: SearchResults,
        temporal_refs: Optional[List[Dict[str, Any]]] = None
    ) -> List[RankedFile]:
        """
        Rank files by relevance to query.
        
        Args:
            query: User query
            search_results: Results from semantic search
            temporal_refs: Temporal references from query analysis
            
        Returns:
            List of ranked files sorted by relevance score
        """
        logger.info(f"Ranking files for query: {query}")
        
        # Extract unique files from search results
        file_scores = {}  # file_id -> {semantic_score, metadata}
        
        for result in search_results.results:
            file_id = result.file_id
            
            if file_id not in file_scores:
                # Get file metadata
                file_metadata_dict = self.metadata_storage.get_file_metadata(file_id)
                
                if not file_metadata_dict:
                    logger.warning(f"File metadata not found: {file_id}")
                    continue
                
                # Convert to FileMetadata object
                file_metadata = self._dict_to_file_metadata(file_metadata_dict)
                
                file_scores[file_id] = {
                    "semantic_score": result.score,
                    "metadata": file_metadata,
                    "max_score": result.score
                }
            else:
                # Update with higher score if found
                if result.score > file_scores[file_id]["max_score"]:
                    file_scores[file_id]["max_score"] = result.score
                    file_scores[file_id]["semantic_score"] = result.score
        
        # Calculate scores for each file
        ranked_files = []
        
        for file_id, data in file_scores.items():
            file_metadata = data["metadata"]
            semantic_score = data["semantic_score"]
            
            # Calculate metadata score
            metadata_score = self._calculate_metadata_score(
                file_metadata,
                query,
                temporal_refs
            )
            
            # Calculate preference score
            preference_score = self._calculate_preference_score(
                file_metadata,
                query
            )
            
            # Calculate final relevance score
            relevance_score = (
                semantic_score * self.SEMANTIC_WEIGHT +
                metadata_score * self.METADATA_WEIGHT +
                preference_score * self.PREFERENCE_WEIGHT
            )
            
            ranked_file = RankedFile(
                file_metadata=file_metadata,
                relevance_score=relevance_score,
                semantic_score=semantic_score,
                metadata_score=metadata_score,
                preference_score=preference_score
            )
            
            ranked_files.append(ranked_file)
            
            logger.debug(
                f"File: {file_metadata.name}, "
                f"Relevance: {relevance_score:.3f} "
                f"(semantic: {semantic_score:.3f}, "
                f"metadata: {metadata_score:.3f}, "
                f"preference: {preference_score:.3f})"
            )
        
        # Sort by relevance score descending
        ranked_files.sort(key=lambda x: x.relevance_score, reverse=True)
        
        logger.info(f"Ranked {len(ranked_files)} files")
        return ranked_files
    
    def select_file(
        self,
        ranked_files: List[RankedFile],
        threshold: float = AUTO_SELECT_THRESHOLD
    ) -> FileSelection:
        """
        Select file or request clarification.
        
        Args:
            ranked_files: List of ranked files
            threshold: Confidence threshold for automatic selection
            
        Returns:
            FileSelection with selected file or candidates
        """
        if not ranked_files:
            logger.warning("No files to select from")
            return FileSelection(
                selected_file=None,
                candidates=[],
                requires_clarification=True,
                confidence=0.0,
                allow_none_option=True
            )
        
        top_file = ranked_files[0]
        confidence = top_file.relevance_score
        
        # Automatic selection if confidence is high
        if confidence >= threshold:
            logger.info(
                f"Auto-selected file: {top_file.file_metadata.name} "
                f"(confidence: {confidence:.3f})"
            )
            return FileSelection(
                selected_file=top_file,
                candidates=[top_file],
                requires_clarification=False,
                confidence=confidence,
                allow_none_option=False
            )
        
        # Request clarification with top 3 candidates
        top_candidates = ranked_files[:3]
        
        logger.info(
            f"Clarification needed (confidence: {confidence:.3f}). "
            f"Presenting {len(top_candidates)} candidates"
        )
        
        return FileSelection(
            selected_file=None,
            candidates=top_candidates,
            requires_clarification=True,
            confidence=confidence,
            allow_none_option=True
        )
    
    def handle_user_selection(
        self,
        query: str,
        candidates: List[RankedFile],
        user_choice: int
    ) -> Optional[RankedFile]:
        """
        Handle user's file selection from candidates.
        
        Args:
            query: Original query
            candidates: List of candidate files
            user_choice: User's choice (0-based index, -1 for "none of these")
            
        Returns:
            Selected RankedFile or None if user chose "none of these"
        """
        # Handle "none of these" option
        if user_choice == -1:
            logger.info("User selected 'none of these' option")
            return None
        
        # Validate choice
        if user_choice < 0 or user_choice >= len(candidates):
            logger.warning(f"Invalid user choice: {user_choice}")
            return None
        
        # Get selected file
        selected_file = candidates[user_choice]
        
        # Record preference
        self.preference_manager.record_preference(
            query=query,
            file_id=selected_file.file_metadata.file_id
        )
        
        logger.info(
            f"User selected file: {selected_file.file_metadata.name} "
            f"(choice {user_choice + 1}/{len(candidates)})"
        )
        
        return selected_file
    
    def _calculate_metadata_score(
        self,
        file_metadata: FileMetadata,
        query: str,
        temporal_refs: Optional[List[Dict[str, Any]]] = None
    ) -> float:
        """
        Calculate metadata match score.
        
        Factors:
        - Date matching (if query contains dates)
        - Path matching (if query mentions folders)
        - Recency (newer files slightly preferred)
        
        Args:
            file_metadata: File metadata
            query: User query
            temporal_refs: Temporal references from query
            
        Returns:
            Metadata score (0-1)
        """
        score = 0.0
        factors = 0
        
        # Date matching (40% of metadata score)
        if temporal_refs:
            date_score = self._calculate_date_match_score(
                file_metadata,
                temporal_refs
            )
            score += date_score * 0.4
            factors += 0.4
        
        # Path matching (30% of metadata score)
        path_score = self._calculate_path_match_score(file_metadata, query)
        score += path_score * 0.3
        factors += 0.3
        
        # Recency score (30% of metadata score)
        recency_score = self._calculate_recency_score(file_metadata)
        score += recency_score * 0.3
        factors += 0.3
        
        # Normalize if not all factors were used
        if factors > 0:
            score = score / factors
        
        return min(1.0, max(0.0, score))
    
    def _calculate_date_match_score(
        self,
        file_metadata: FileMetadata,
        temporal_refs: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate date matching score.
        
        Args:
            file_metadata: File metadata
            temporal_refs: Temporal references from query
            
        Returns:
            Date match score (0-1)
        """
        # Parse dates from file name
        parsed_dates = self.date_parser.parse_dates_from_filename(
            file_metadata.name
        )
        
        if not parsed_dates:
            # Try parsing from path
            parsed_dates = self.date_parser.parse_dates_from_filename(
                file_metadata.path
            )
        
        if not parsed_dates:
            return 0.0
        
        # Check if any parsed date matches temporal references
        max_score = 0.0
        
        for parsed_date in parsed_dates:
            for temporal_ref in temporal_refs:
                match_score = self.date_parser.match_dates(
                    parsed_date,
                    temporal_ref
                )
                max_score = max(max_score, match_score)
        
        return max_score
    
    def _calculate_path_match_score(
        self,
        file_metadata: FileMetadata,
        query: str
    ) -> float:
        """
        Calculate path matching score.
        
        Args:
            file_metadata: File metadata
            query: User query
            
        Returns:
            Path match score (0-1)
        """
        query_lower = query.lower()
        path_lower = file_metadata.path.lower()
        name_lower = file_metadata.name.lower()
        
        # Check for path components in query
        path_parts = [p for p in path_lower.split('/') if p]
        
        matches = 0
        for part in path_parts:
            if part in query_lower:
                matches += 1
        
        # Check for file name in query
        name_without_ext = name_lower.rsplit('.', 1)[0]
        if name_without_ext in query_lower:
            matches += 2  # File name match is more important
        
        # Normalize score
        max_possible = len(path_parts) + 2
        score = matches / max_possible if max_possible > 0 else 0.0
        
        return min(1.0, score)
    
    def _calculate_recency_score(self, file_metadata: FileMetadata) -> float:
        """
        Calculate recency score (newer files slightly preferred).
        
        Args:
            file_metadata: File metadata
            
        Returns:
            Recency score (0-1)
        """
        # Calculate days since modification
        now = datetime.now()
        
        # Handle timezone-aware datetime
        modified_time = file_metadata.modified_time
        if modified_time.tzinfo is not None:
            # Make now timezone-aware to match
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        
        days_old = (now - modified_time).days
        
        # Score decreases gradually over time
        # Files modified within 30 days get full score
        # Score decreases to 0.5 at 365 days
        if days_old <= 30:
            return 1.0
        elif days_old <= 365:
            return 1.0 - (days_old - 30) / (365 - 30) * 0.5
        else:
            return 0.5
    
    def _calculate_preference_score(
        self,
        file_metadata: FileMetadata,
        query: str
    ) -> float:
        """
        Calculate user preference score based on history.
        
        Args:
            file_metadata: File metadata
            query: User query
            
        Returns:
            Preference score (0-1)
        """
        try:
            preferences = self.preference_manager.get_preferences(query)
            
            # Check if this file was previously selected for similar queries
            for pref in preferences:
                if pref["file_id"] == file_metadata.file_id:
                    # Apply exponential decay based on age
                    return pref["score"]
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Error calculating preference score: {e}")
            return 0.0
    
    def _dict_to_file_metadata(self, data: Dict[str, Any]) -> FileMetadata:
        """
        Convert dictionary to FileMetadata object.
        
        Args:
            data: Dictionary with file metadata
            
        Returns:
            FileMetadata object
        """
        from src.models.domain_models import FileStatus
        
        # Parse datetime strings
        modified_time = data["modified_time"]
        if isinstance(modified_time, str):
            modified_time = datetime.fromisoformat(modified_time)
        
        indexed_at = data.get("indexed_at")
        if indexed_at and isinstance(indexed_at, str):
            indexed_at = datetime.fromisoformat(indexed_at)
        
        return FileMetadata(
            file_id=data["file_id"],
            name=data["name"],
            path=data["path"],
            mime_type=data.get("mime_type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            size=data.get("size", 0),
            modified_time=modified_time,
            md5_checksum=data.get("md5_checksum", ""),
            status=FileStatus(data.get("status", "indexed")),
            indexed_at=indexed_at
        )
