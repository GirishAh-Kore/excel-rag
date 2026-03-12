"""
Extraction quality scoring for Excel files.

This module provides the ExtractionQualityScorer class that computes
quality scores for extracted Excel data based on multiple factors
including data completeness, structure clarity, header detection,
data presence, and error counts.

Supports Requirements:
- 22.1: Compute Extraction_Quality_Score (0-1) based on data_completeness,
        structure_clarity, header_detection_confidence, and error_count
- 22.2: Display quality scores at file, sheet, and chunk levels
- 22.3: Flag files with quality < 0.5 as potentially problematic
- 22.4: Factor data quality scores into confidence calculations for answers
"""

from dataclasses import dataclass
from typing import Optional, Protocol

from src.models.excel_features import (
    ExtractionQuality,
    ExtractionWarning,
    ExtractedSheetData,
)


# Quality score threshold for flagging problematic files
PROBLEMATIC_QUALITY_THRESHOLD = 0.5


@dataclass(frozen=True)
class QualityScorerConfig:
    """
    Configuration for quality score computation.
    
    Defines the weights used in the quality score formula and
    thresholds for various quality indicators.
    
    Attributes:
        has_headers_weight: Weight for header detection (default 0.25).
        has_data_weight: Weight for data presence (default 0.25).
        data_completeness_weight: Weight for data completeness (default 0.25).
        structure_clarity_weight: Weight for structure clarity (default 0.25).
        error_penalty: Penalty per error (default 0.1).
        max_error_penalty: Maximum total error penalty (default 0.5).
        problematic_threshold: Threshold below which files are flagged (default 0.5).
        sample_rows_for_completeness: Number of rows to sample for completeness (default 100).
        max_columns_for_clarity: Column count for max structure clarity (default 20).
    """
    has_headers_weight: float = 0.25
    has_data_weight: float = 0.25
    data_completeness_weight: float = 0.25
    structure_clarity_weight: float = 0.25
    error_penalty: float = 0.1
    max_error_penalty: float = 0.5
    problematic_threshold: float = PROBLEMATIC_QUALITY_THRESHOLD
    sample_rows_for_completeness: int = 100
    max_columns_for_clarity: int = 20
    
    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate weights sum to 1.0
        total_weight = (
            self.has_headers_weight +
            self.has_data_weight +
            self.data_completeness_weight +
            self.structure_clarity_weight
        )
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Quality weights must sum to 1.0, got {total_weight}"
            )
        
        # Validate individual weights are in valid range
        for name, value in [
            ("has_headers_weight", self.has_headers_weight),
            ("has_data_weight", self.has_data_weight),
            ("data_completeness_weight", self.data_completeness_weight),
            ("structure_clarity_weight", self.structure_clarity_weight),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"{name} must be between 0.0 and 1.0, got {value}"
                )
        
        # Validate penalties
        if self.error_penalty < 0.0:
            raise ValueError(
                f"error_penalty must be non-negative, got {self.error_penalty}"
            )
        if self.max_error_penalty < 0.0:
            raise ValueError(
                f"max_error_penalty must be non-negative, got {self.max_error_penalty}"
            )
        
        # Validate threshold
        if not 0.0 <= self.problematic_threshold <= 1.0:
            raise ValueError(
                f"problematic_threshold must be between 0.0 and 1.0, "
                f"got {self.problematic_threshold}"
            )
        
        # Validate sample size
        if self.sample_rows_for_completeness < 1:
            raise ValueError(
                f"sample_rows_for_completeness must be at least 1, "
                f"got {self.sample_rows_for_completeness}"
            )
        
        # Validate max columns
        if self.max_columns_for_clarity < 1:
            raise ValueError(
                f"max_columns_for_clarity must be at least 1, "
                f"got {self.max_columns_for_clarity}"
            )


@dataclass
class QualityAssessment:
    """
    Complete quality assessment result for an extraction.
    
    Contains the quality metrics, overall score, and flags indicating
    whether the extraction is considered problematic.
    
    Attributes:
        quality: The ExtractionQuality object with all metrics.
        is_problematic: Whether the quality score is below threshold.
        issues: List of identified quality issues.
        recommendations: List of recommendations for improving quality.
    """
    quality: ExtractionQuality
    is_problematic: bool
    issues: list[str]
    recommendations: list[str]
    
    @property
    def score(self) -> float:
        """Get the overall quality score."""
        return self.quality.score


class QualityMetricsProvider(Protocol):
    """
    Protocol for providing quality metrics from extracted data.
    
    This protocol allows different data sources to provide the
    metrics needed for quality scoring.
    """
    
    def get_sheets(self) -> list[ExtractedSheetData]:
        """Get the list of extracted sheets."""
        ...
    
    def get_warnings(self) -> list[ExtractionWarning]:
        """Get the list of extraction warnings."""
        ...


class ExtractionQualityScorer:
    """
    Computes quality scores for extracted Excel data.
    
    The quality score is computed from multiple factors:
    - data_completeness: Ratio of non-empty cells to total cells
    - structure_clarity: How well-structured the data is (based on column consistency)
    - has_headers: Whether headers were detected
    - has_data: Whether actual data rows were found
    - error_count: Number of errors encountered during extraction
    
    The score is always in the range [0.0, 1.0]. Files with quality < 0.5
    are flagged as potentially problematic.
    
    This class follows the Single Responsibility Principle by focusing
    solely on quality score computation. All dependencies are injected
    via the constructor following the Dependency Inversion Principle.
    
    Supports Requirements 22.1, 22.2, 22.3, 22.4.
    
    Example:
        >>> config = QualityScorerConfig()
        >>> scorer = ExtractionQualityScorer(config)
        >>> assessment = scorer.assess_quality(sheets, warnings)
        >>> print(f"Quality: {assessment.score}, Problematic: {assessment.is_problematic}")
    """
    
    def __init__(self, config: Optional[QualityScorerConfig] = None) -> None:
        """
        Initialize the quality scorer with configuration.
        
        Args:
            config: Optional configuration for quality scoring.
                If not provided, uses default configuration.
        """
        self._config = config or QualityScorerConfig()
    
    @property
    def config(self) -> QualityScorerConfig:
        """Get the scorer configuration."""
        return self._config
    
    def compute_quality_score(
        self,
        data_completeness: float,
        structure_clarity: float,
        has_headers: bool,
        has_data: bool,
        error_count: int
    ) -> float:
        """
        Compute the overall quality score from individual metrics.
        
        The score is computed using a weighted formula:
        score = (has_headers_weight * has_headers) +
                (has_data_weight * has_data) +
                (data_completeness_weight * data_completeness) +
                (structure_clarity_weight * structure_clarity) -
                min(error_penalty * error_count, max_error_penalty)
        
        Args:
            data_completeness: Ratio of non-empty cells (0.0 to 1.0).
            structure_clarity: Structure clarity score (0.0 to 1.0).
            has_headers: Whether headers were detected.
            has_data: Whether data rows were found.
            error_count: Number of errors encountered.
        
        Returns:
            Quality score in range [0.0, 1.0].
        
        Raises:
            ValueError: If input values are out of valid ranges.
        
        Supports Requirement 22.1: Compute Extraction_Quality_Score (0-1).
        """
        # Validate inputs
        if not 0.0 <= data_completeness <= 1.0:
            raise ValueError(
                f"data_completeness must be between 0.0 and 1.0, "
                f"got {data_completeness}"
            )
        if not 0.0 <= structure_clarity <= 1.0:
            raise ValueError(
                f"structure_clarity must be between 0.0 and 1.0, "
                f"got {structure_clarity}"
            )
        if error_count < 0:
            raise ValueError(
                f"error_count must be non-negative, got {error_count}"
            )
        
        # Compute base score from weighted components
        base_score = (
            (self._config.has_headers_weight * (1.0 if has_headers else 0.0)) +
            (self._config.has_data_weight * (1.0 if has_data else 0.0)) +
            (self._config.data_completeness_weight * data_completeness) +
            (self._config.structure_clarity_weight * structure_clarity)
        )
        
        # Apply error penalty
        error_penalty = min(
            self._config.error_penalty * error_count,
            self._config.max_error_penalty
        )
        
        # Compute final score, ensuring it stays in [0.0, 1.0]
        score = max(0.0, min(1.0, base_score - error_penalty))
        
        return score
    
    def calculate_data_completeness(
        self,
        sheets: list[ExtractedSheetData]
    ) -> float:
        """
        Calculate data completeness from extracted sheets.
        
        Data completeness is the ratio of non-empty cells to total cells,
        sampled from the first N rows of each sheet (configurable).
        
        Args:
            sheets: List of extracted sheet data.
        
        Returns:
            Data completeness ratio (0.0 to 1.0).
        """
        if not sheets:
            return 0.0
        
        total_cells = 0
        non_empty_cells = 0
        sample_rows = self._config.sample_rows_for_completeness
        
        for sheet in sheets:
            # Sample first N rows
            for row in sheet.data[:sample_rows]:
                for value in row:
                    total_cells += 1
                    if value is not None and value != "":
                        non_empty_cells += 1
        
        if total_cells == 0:
            return 0.0
        
        return non_empty_cells / total_cells
    
    def calculate_structure_clarity(
        self,
        sheets: list[ExtractedSheetData]
    ) -> float:
        """
        Calculate structure clarity from extracted sheets.
        
        Structure clarity is based on column consistency across sheets.
        A higher number of columns (up to a maximum) indicates clearer
        structure. The score is normalized to [0.0, 1.0].
        
        Args:
            sheets: List of extracted sheet data.
        
        Returns:
            Structure clarity score (0.0 to 1.0).
        """
        if not sheets:
            return 0.0
        
        total_sheets = len(sheets)
        avg_columns = sum(s.column_count for s in sheets) / total_sheets
        
        # Normalize to [0.0, 1.0] based on max columns config
        clarity = min(avg_columns / self._config.max_columns_for_clarity, 1.0)
        
        return clarity
    
    def count_errors(self, warnings: list[ExtractionWarning]) -> int:
        """
        Count the number of error-level warnings.
        
        Args:
            warnings: List of extraction warnings.
        
        Returns:
            Number of warnings with severity "error".
        """
        return len([w for w in warnings if w.severity == "error"])
    
    def count_warnings(self, warnings: list[ExtractionWarning]) -> int:
        """
        Count the total number of warnings.
        
        Args:
            warnings: List of extraction warnings.
        
        Returns:
            Total number of warnings.
        """
        return len(warnings)
    
    def is_problematic(self, quality_score: float) -> bool:
        """
        Determine if a quality score indicates a problematic file.
        
        Args:
            quality_score: The quality score to evaluate.
        
        Returns:
            True if the score is below the problematic threshold.
        
        Supports Requirement 22.3: Flag files with quality < 0.5 as
        potentially problematic.
        """
        return quality_score < self._config.problematic_threshold
    
    def identify_issues(
        self,
        data_completeness: float,
        structure_clarity: float,
        has_headers: bool,
        has_data: bool,
        error_count: int,
        warning_count: int
    ) -> list[str]:
        """
        Identify specific quality issues based on metrics.
        
        Args:
            data_completeness: Data completeness ratio.
            structure_clarity: Structure clarity score.
            has_headers: Whether headers were detected.
            has_data: Whether data rows were found.
            error_count: Number of errors.
            warning_count: Number of warnings.
        
        Returns:
            List of identified issue descriptions.
        """
        issues: list[str] = []
        
        if not has_headers:
            issues.append("No headers detected in the data")
        
        if not has_data:
            issues.append("No data rows found in the file")
        
        if data_completeness < 0.5:
            issues.append(
                f"Low data completeness ({data_completeness:.1%}): "
                "many cells are empty"
            )
        
        if structure_clarity < 0.3:
            issues.append(
                f"Poor structure clarity ({structure_clarity:.1%}): "
                "data structure is unclear"
            )
        
        if error_count > 0:
            issues.append(
                f"{error_count} extraction error(s) encountered"
            )
        
        if warning_count > 5:
            issues.append(
                f"High number of warnings ({warning_count})"
            )
        
        return issues
    
    def generate_recommendations(
        self,
        data_completeness: float,
        structure_clarity: float,
        has_headers: bool,
        has_data: bool,
        error_count: int
    ) -> list[str]:
        """
        Generate recommendations for improving extraction quality.
        
        Args:
            data_completeness: Data completeness ratio.
            structure_clarity: Structure clarity score.
            has_headers: Whether headers were detected.
            has_data: Whether data rows were found.
            error_count: Number of errors.
        
        Returns:
            List of recommendations.
        """
        recommendations: list[str] = []
        
        if not has_headers:
            recommendations.append(
                "Consider adding a header row to improve data structure recognition"
            )
        
        if not has_data:
            recommendations.append(
                "Verify the file contains data rows below the header"
            )
        
        if data_completeness < 0.5:
            recommendations.append(
                "Review the file for excessive empty cells or sparse data"
            )
        
        if structure_clarity < 0.3:
            recommendations.append(
                "Consider restructuring the data with consistent columns"
            )
        
        if error_count > 0:
            recommendations.append(
                "Review extraction errors and consider using a different "
                "extraction strategy"
            )
        
        return recommendations
    
    def assess_quality(
        self,
        sheets: list[ExtractedSheetData],
        warnings: list[ExtractionWarning]
    ) -> QualityAssessment:
        """
        Perform a complete quality assessment of extracted data.
        
        This is the main entry point for quality assessment. It computes
        all metrics, the overall score, identifies issues, and generates
        recommendations.
        
        Args:
            sheets: List of extracted sheet data.
            warnings: List of extraction warnings.
        
        Returns:
            QualityAssessment containing all quality information.
        
        Supports Requirements 22.1, 22.2, 22.3.
        """
        # Handle empty sheets case
        if not sheets:
            error_count = self.count_errors(warnings)
            warning_count = self.count_warnings(warnings)
            
            quality = ExtractionQuality(
                score=0.0,
                data_completeness=0.0,
                structure_clarity=0.0,
                has_headers=False,
                has_data=False,
                error_count=error_count,
                warning_count=warning_count,
            )
            
            return QualityAssessment(
                quality=quality,
                is_problematic=True,
                issues=["No sheets were extracted from the file"],
                recommendations=["Verify the file is a valid Excel file with data"],
            )
        
        # Calculate individual metrics
        data_completeness = self.calculate_data_completeness(sheets)
        structure_clarity = self.calculate_structure_clarity(sheets)
        has_headers = any(s.has_headers for s in sheets)
        has_data = any(s.row_count > 0 for s in sheets)
        error_count = self.count_errors(warnings)
        warning_count = self.count_warnings(warnings)
        
        # Compute overall score
        score = self.compute_quality_score(
            data_completeness=data_completeness,
            structure_clarity=structure_clarity,
            has_headers=has_headers,
            has_data=has_data,
            error_count=error_count,
        )
        
        # Create quality object
        quality = ExtractionQuality(
            score=score,
            data_completeness=data_completeness,
            structure_clarity=structure_clarity,
            has_headers=has_headers,
            has_data=has_data,
            error_count=error_count,
            warning_count=warning_count,
        )
        
        # Determine if problematic
        problematic = self.is_problematic(score)
        
        # Identify issues and recommendations
        issues = self.identify_issues(
            data_completeness=data_completeness,
            structure_clarity=structure_clarity,
            has_headers=has_headers,
            has_data=has_data,
            error_count=error_count,
            warning_count=warning_count,
        )
        
        recommendations = self.generate_recommendations(
            data_completeness=data_completeness,
            structure_clarity=structure_clarity,
            has_headers=has_headers,
            has_data=has_data,
            error_count=error_count,
        )
        
        return QualityAssessment(
            quality=quality,
            is_problematic=problematic,
            issues=issues,
            recommendations=recommendations,
        )
    
    def compute_sheet_quality(
        self,
        sheet: ExtractedSheetData,
        warnings: Optional[list[ExtractionWarning]] = None
    ) -> ExtractionQuality:
        """
        Compute quality score for a single sheet.
        
        Args:
            sheet: The extracted sheet data.
            warnings: Optional list of warnings specific to this sheet.
        
        Returns:
            ExtractionQuality for the sheet.
        
        Supports Requirement 22.2: Display quality scores at sheet level.
        """
        warnings = warnings or []
        
        # Calculate metrics for single sheet
        data_completeness = self.calculate_data_completeness([sheet])
        structure_clarity = self.calculate_structure_clarity([sheet])
        error_count = self.count_errors(warnings)
        warning_count = self.count_warnings(warnings)
        
        score = self.compute_quality_score(
            data_completeness=data_completeness,
            structure_clarity=structure_clarity,
            has_headers=sheet.has_headers,
            has_data=sheet.row_count > 0,
            error_count=error_count,
        )
        
        return ExtractionQuality(
            score=score,
            data_completeness=data_completeness,
            structure_clarity=structure_clarity,
            has_headers=sheet.has_headers,
            has_data=sheet.row_count > 0,
            error_count=error_count,
            warning_count=warning_count,
        )
