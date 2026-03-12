"""
Relationship Detector for Intelligence Module

Detects relationships between Excel files based on:
- Common column names and data patterns
- Implicit join opportunities across files
- Related file suggestions during selection

Supports Requirements 36.1, 36.2, 36.3, 36.4.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


class RelationshipType(str, Enum):
    """Type of relationship between files/columns."""
    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    COMMON_COLUMN = "common_column"
    LOOKUP = "lookup"
    HIERARCHICAL = "hierarchical"
    TEMPORAL = "temporal"


class JoinType(str, Enum):
    """Type of join operation for related data."""
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    FULL = "full"
    CROSS = "cross"


@dataclass
class RelationshipDetectorConfig:
    """
    Configuration for RelationshipDetector.
    
    Attributes:
        min_name_similarity: Minimum similarity for column name matching.
        min_value_overlap: Minimum value overlap ratio for relationship.
        sample_size: Number of values to sample for comparison.
        detect_temporal: Whether to detect temporal relationships.
    """
    min_name_similarity: float = 0.8
    min_value_overlap: float = 0.3
    sample_size: int = 100
    detect_temporal: bool = True
    
    def __post_init__(self) -> None:
        """Validate configuration."""
        if not 0.0 <= self.min_name_similarity <= 1.0:
            raise ValueError(f"min_name_similarity must be 0.0-1.0, got {self.min_name_similarity}")
        if not 0.0 <= self.min_value_overlap <= 1.0:
            raise ValueError(f"min_value_overlap must be 0.0-1.0, got {self.min_value_overlap}")


@dataclass
class ColumnInfo:
    """Information about a column for relationship detection."""
    file_id: str
    file_name: str
    sheet_name: str
    column_name: str
    column_index: int
    data_type: str
    sample_values: list[Any] = field(default_factory=list)
    unique_count: int = 0
    null_count: int = 0
    total_count: int = 0


@dataclass
class DetectedRelationship:
    """
    A detected relationship between columns/files.
    
    Attributes:
        relationship_type: Type of relationship detected.
        source_column: Source column information.
        target_column: Target column information.
        confidence: Confidence score for the relationship (0.0 to 1.0).
        suggested_join: Suggested join type for queries.
        overlap_ratio: Ratio of overlapping values.
        message: Human-readable description.
        metadata: Additional relationship metadata.
    """
    relationship_type: RelationshipType
    source_column: ColumnInfo
    target_column: ColumnInfo
    confidence: float
    suggested_join: JoinType
    overlap_ratio: float
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate relationship."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        if not 0.0 <= self.overlap_ratio <= 1.0:
            raise ValueError(f"overlap_ratio must be 0.0-1.0, got {self.overlap_ratio}")


@dataclass
class RelatedFileInfo:
    """Information about a related file."""
    file_id: str
    file_name: str
    relationships: list[DetectedRelationship]
    relevance_score: float
    
    @property
    def relationship_count(self) -> int:
        """Number of relationships with this file."""
        return len(self.relationships)


@dataclass
class RelationshipReport:
    """
    Complete relationship detection report.
    
    Attributes:
        files_analyzed: Number of files analyzed.
        relationships: All detected relationships.
        related_files: Files grouped by relationships.
        join_suggestions: Suggested joins for queries.
    """
    files_analyzed: int
    relationships: list[DetectedRelationship]
    related_files: dict[str, list[RelatedFileInfo]]
    join_suggestions: list[dict[str, Any]]
    
    @property
    def relationship_count(self) -> int:
        """Total number of relationships detected."""
        return len(self.relationships)


class MetadataStoreProtocol(Protocol):
    """Protocol for metadata store dependency."""
    
    def get_file_columns(self, file_id: str) -> list[dict[str, Any]]:
        """Get column information for a file."""
        ...
    
    def get_column_sample(
        self,
        file_id: str,
        column_name: str,
        sample_size: int,
    ) -> list[Any]:
        """Get sample values from a column."""
        ...


class RelationshipDetector:
    """
    Detects relationships between Excel files and columns.
    
    Analyzes column names, data types, and value patterns to identify
    potential relationships that can be used for implicit joins.
    
    All dependencies are injected via constructor following DIP.
    
    Supports Requirements 36.1, 36.2, 36.3, 36.4.
    """
    
    # Common key column name patterns
    KEY_PATTERNS: list[str] = [
        "id", "key", "code", "number", "no", "num",
        "_id", "_key", "_code", "_no",
    ]
    
    # Common foreign key suffixes
    FK_SUFFIXES: list[str] = [
        "_id", "_key", "_code", "_fk", "_ref",
        "id", "key", "code",
    ]
    
    def __init__(
        self,
        config: Optional[RelationshipDetectorConfig] = None,
        metadata_store: Optional[MetadataStoreProtocol] = None,
    ) -> None:
        """
        Initialize RelationshipDetector.
        
        Args:
            config: Detector configuration. Uses defaults if not provided.
            metadata_store: Optional metadata store for column information.
        """
        self._config = config or RelationshipDetectorConfig()
        self._metadata_store = metadata_store
        logger.info(
            f"RelationshipDetector initialized with "
            f"min_name_similarity={self._config.min_name_similarity}"
        )
    
    def detect_relationships(
        self,
        columns: list[ColumnInfo],
    ) -> list[DetectedRelationship]:
        """
        Detect relationships between columns.
        
        Args:
            columns: List of column information to analyze.
        
        Returns:
            List of detected relationships.
        """
        if len(columns) < 2:
            return []
        
        relationships: list[DetectedRelationship] = []
        
        # Compare each pair of columns from different files
        for i, col1 in enumerate(columns):
            for col2 in columns[i + 1:]:
                # Skip columns from the same file
                if col1.file_id == col2.file_id:
                    continue
                
                # Check for relationship
                relationship = self._detect_column_relationship(col1, col2)
                if relationship:
                    relationships.append(relationship)
        
        # Sort by confidence
        relationships.sort(key=lambda r: r.confidence, reverse=True)
        
        logger.info(f"Detected {len(relationships)} relationships among {len(columns)} columns")
        return relationships
    
    def find_related_files(
        self,
        file_id: str,
        all_columns: list[ColumnInfo],
    ) -> list[RelatedFileInfo]:
        """
        Find files related to a given file.
        
        Args:
            file_id: ID of the file to find relations for.
            all_columns: All columns across all files.
        
        Returns:
            List of related files with their relationships.
        """
        # Get columns for the target file
        target_columns = [c for c in all_columns if c.file_id == file_id]
        other_columns = [c for c in all_columns if c.file_id != file_id]
        
        if not target_columns or not other_columns:
            return []
        
        # Find relationships
        file_relationships: dict[str, list[DetectedRelationship]] = {}
        
        for target_col in target_columns:
            for other_col in other_columns:
                relationship = self._detect_column_relationship(target_col, other_col)
                if relationship:
                    other_file_id = other_col.file_id
                    if other_file_id not in file_relationships:
                        file_relationships[other_file_id] = []
                    file_relationships[other_file_id].append(relationship)
        
        # Build related file info
        related_files: list[RelatedFileInfo] = []
        
        for other_file_id, rels in file_relationships.items():
            # Get file name from first relationship
            file_name = rels[0].target_column.file_name
            
            # Calculate relevance score
            avg_confidence = sum(r.confidence for r in rels) / len(rels)
            relevance = min(1.0, avg_confidence * (1 + 0.1 * len(rels)))
            
            related_files.append(RelatedFileInfo(
                file_id=other_file_id,
                file_name=file_name,
                relationships=rels,
                relevance_score=relevance,
            ))
        
        # Sort by relevance
        related_files.sort(key=lambda f: f.relevance_score, reverse=True)
        
        return related_files
    
    def suggest_join(
        self,
        relationship: DetectedRelationship,
    ) -> dict[str, Any]:
        """
        Suggest a join operation for a relationship.
        
        Args:
            relationship: The detected relationship.
        
        Returns:
            Dictionary with join suggestion details.
        """
        source = relationship.source_column
        target = relationship.target_column
        
        return {
            "join_type": relationship.suggested_join.value,
            "source_file": source.file_name,
            "source_column": source.column_name,
            "target_file": target.file_name,
            "target_column": target.column_name,
            "confidence": relationship.confidence,
            "sql_hint": (
                f"SELECT * FROM [{source.file_name}] "
                f"{relationship.suggested_join.value.upper()} JOIN [{target.file_name}] "
                f"ON [{source.file_name}].[{source.column_name}] = "
                f"[{target.file_name}].[{target.column_name}]"
            ),
        }
    
    def generate_report(
        self,
        columns: list[ColumnInfo],
    ) -> RelationshipReport:
        """
        Generate a complete relationship report.
        
        Args:
            columns: All columns to analyze.
        
        Returns:
            RelationshipReport with all findings.
        """
        # Get unique files
        file_ids = set(c.file_id for c in columns)
        
        # Detect all relationships
        relationships = self.detect_relationships(columns)
        
        # Group related files
        related_files: dict[str, list[RelatedFileInfo]] = {}
        for file_id in file_ids:
            related = self.find_related_files(file_id, columns)
            if related:
                related_files[file_id] = related
        
        # Generate join suggestions
        join_suggestions = [
            self.suggest_join(rel) for rel in relationships[:10]  # Top 10
        ]
        
        return RelationshipReport(
            files_analyzed=len(file_ids),
            relationships=relationships,
            related_files=related_files,
            join_suggestions=join_suggestions,
        )

    
    def _detect_column_relationship(
        self,
        col1: ColumnInfo,
        col2: ColumnInfo,
    ) -> Optional[DetectedRelationship]:
        """Detect relationship between two columns."""
        # Check name similarity
        name_similarity = self._calculate_name_similarity(
            col1.column_name, col2.column_name
        )
        
        # Check if names suggest a key relationship
        is_key_pattern = self._is_key_column(col1.column_name) or self._is_key_column(col2.column_name)
        
        # Check value overlap
        overlap_ratio = self._calculate_value_overlap(col1.sample_values, col2.sample_values)
        
        # Determine if there's a relationship
        if name_similarity < self._config.min_name_similarity and overlap_ratio < self._config.min_value_overlap:
            return None
        
        # Calculate confidence
        confidence = self._calculate_relationship_confidence(
            name_similarity, overlap_ratio, is_key_pattern, col1, col2
        )
        
        if confidence < 0.5:
            return None
        
        # Determine relationship type
        rel_type = self._determine_relationship_type(col1, col2, name_similarity, overlap_ratio)
        
        # Determine suggested join type
        join_type = self._suggest_join_type(col1, col2, overlap_ratio)
        
        # Determine source and target (higher uniqueness is typically the source/primary)
        if col1.unique_count >= col2.unique_count:
            source, target = col1, col2
        else:
            source, target = col2, col1
        
        return DetectedRelationship(
            relationship_type=rel_type,
            source_column=source,
            target_column=target,
            confidence=confidence,
            suggested_join=join_type,
            overlap_ratio=overlap_ratio,
            message=self._generate_relationship_message(rel_type, source, target),
            metadata={
                "name_similarity": name_similarity,
                "is_key_pattern": is_key_pattern,
            },
        )
    
    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between column names."""
        # Normalize names
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        
        # Exact match
        if n1 == n2:
            return 1.0
        
        # Check for common suffixes/prefixes
        for suffix in self.FK_SUFFIXES:
            n1_base = n1.rstrip(suffix) if n1.endswith(suffix) else n1
            n2_base = n2.rstrip(suffix) if n2.endswith(suffix) else n2
            if n1_base == n2_base and n1_base:
                return 0.95
        
        # Levenshtein-like similarity
        return self._string_similarity(n1, n2)
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calculate string similarity using character overlap."""
        if not s1 or not s2:
            return 0.0
        
        # Use set-based similarity for simplicity
        set1 = set(s1)
        set2 = set(s2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        
        # Also consider length similarity
        len_ratio = min(len(s1), len(s2)) / max(len(s1), len(s2))
        
        return (jaccard + len_ratio) / 2
    
    def _calculate_value_overlap(
        self,
        values1: list[Any],
        values2: list[Any],
    ) -> float:
        """Calculate the overlap ratio between two sets of values."""
        if not values1 or not values2:
            return 0.0
        
        # Convert to sets of strings for comparison
        set1 = {str(v).lower().strip() for v in values1 if v is not None}
        set2 = {str(v).lower().strip() for v in values2 if v is not None}
        
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        smaller_set = min(len(set1), len(set2))
        
        return intersection / smaller_set if smaller_set > 0 else 0.0
    
    def _is_key_column(self, column_name: str) -> bool:
        """Check if column name suggests it's a key column."""
        name_lower = column_name.lower()
        
        for pattern in self.KEY_PATTERNS:
            if pattern in name_lower:
                return True
        
        return False
    
    def _calculate_relationship_confidence(
        self,
        name_similarity: float,
        overlap_ratio: float,
        is_key_pattern: bool,
        col1: ColumnInfo,
        col2: ColumnInfo,
    ) -> float:
        """Calculate overall confidence in the relationship."""
        # Base confidence from name and value similarity
        base_confidence = (name_similarity * 0.4) + (overlap_ratio * 0.4)
        
        # Boost for key patterns
        if is_key_pattern:
            base_confidence += 0.15
        
        # Boost for matching data types
        if col1.data_type == col2.data_type:
            base_confidence += 0.05
        
        # Penalize if one column has very low uniqueness
        if col1.total_count > 0 and col2.total_count > 0:
            uniqueness1 = col1.unique_count / col1.total_count
            uniqueness2 = col2.unique_count / col2.total_count
            
            # Very low uniqueness in both suggests not a good join key
            if uniqueness1 < 0.1 and uniqueness2 < 0.1:
                base_confidence *= 0.7
        
        return min(1.0, base_confidence)
    
    def _determine_relationship_type(
        self,
        col1: ColumnInfo,
        col2: ColumnInfo,
        name_similarity: float,
        overlap_ratio: float,
    ) -> RelationshipType:
        """Determine the type of relationship."""
        # Check for primary/foreign key pattern
        is_pk1 = self._is_primary_key_candidate(col1)
        is_pk2 = self._is_primary_key_candidate(col2)
        
        if is_pk1 and not is_pk2:
            return RelationshipType.PRIMARY_KEY
        elif is_pk2 and not is_pk1:
            return RelationshipType.FOREIGN_KEY
        elif is_pk1 and is_pk2:
            return RelationshipType.COMMON_COLUMN
        
        # Check for lookup relationship
        if overlap_ratio > 0.8 and name_similarity > 0.9:
            return RelationshipType.LOOKUP
        
        # Default to common column
        return RelationshipType.COMMON_COLUMN
    
    def _is_primary_key_candidate(self, col: ColumnInfo) -> bool:
        """Check if column is a primary key candidate."""
        if col.total_count == 0:
            return False
        
        # High uniqueness suggests primary key
        uniqueness = col.unique_count / col.total_count
        
        # Name pattern check
        name_suggests_pk = any(
            pattern in col.column_name.lower()
            for pattern in ["_id", "id", "_pk", "key"]
        )
        
        return uniqueness > 0.95 and name_suggests_pk
    
    def _suggest_join_type(
        self,
        col1: ColumnInfo,
        col2: ColumnInfo,
        overlap_ratio: float,
    ) -> JoinType:
        """Suggest the best join type for the relationship."""
        # High overlap suggests inner join is safe
        if overlap_ratio > 0.8:
            return JoinType.INNER
        
        # Medium overlap - left join to preserve source data
        if overlap_ratio > 0.5:
            return JoinType.LEFT
        
        # Low overlap - full join to see all data
        return JoinType.FULL
    
    def _generate_relationship_message(
        self,
        rel_type: RelationshipType,
        source: ColumnInfo,
        target: ColumnInfo,
    ) -> str:
        """Generate a human-readable relationship message."""
        type_descriptions = {
            RelationshipType.PRIMARY_KEY: "primary key relationship",
            RelationshipType.FOREIGN_KEY: "foreign key relationship",
            RelationshipType.COMMON_COLUMN: "common column",
            RelationshipType.LOOKUP: "lookup relationship",
            RelationshipType.HIERARCHICAL: "hierarchical relationship",
            RelationshipType.TEMPORAL: "temporal relationship",
        }
        
        desc = type_descriptions.get(rel_type, "relationship")
        
        return (
            f"Detected {desc} between "
            f"[{source.file_name}].{source.column_name} and "
            f"[{target.file_name}].{target.column_name}"
        )
