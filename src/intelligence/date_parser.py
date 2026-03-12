"""
Enhanced Date Parser for Intelligence Module

Parses natural language date references with support for:
- Relative dates: "last quarter", "YTD", "past 6 months"
- Absolute dates: "January 2024", "Q1 2024"
- Multiple date formats: MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD
- Fiscal year configurations

Supports Requirements 33.1, 33.4, 33.6.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Optional

import dateparser

logger = logging.getLogger(__name__)


class DateReferenceType(str, Enum):
    """Type of date reference detected."""
    ABSOLUTE_DATE = "absolute_date"
    RELATIVE_DATE = "relative_date"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"
    FISCAL_YEAR = "fiscal_year"
    FISCAL_QUARTER = "fiscal_quarter"
    DATE_RANGE = "date_range"
    YTD = "ytd"
    MTD = "mtd"
    QTD = "qtd"


@dataclass
class FiscalYearConfig:
    """
    Configuration for fiscal year calculations.
    
    Attributes:
        start_month: Month when fiscal year starts (1-12).
        start_day: Day when fiscal year starts (1-31).
    """
    start_month: int = 1
    start_day: int = 1
    
    def __post_init__(self) -> None:
        """Validate fiscal year configuration."""
        if not 1 <= self.start_month <= 12:
            raise ValueError(f"start_month must be 1-12, got {self.start_month}")
        if not 1 <= self.start_day <= 31:
            raise ValueError(f"start_day must be 1-31, got {self.start_day}")


@dataclass
class DateParserConfig:
    """
    Configuration for DateParser.
    
    Attributes:
        fiscal_year: Fiscal year configuration.
        default_date_format: Preferred date format for ambiguous dates.
        prefer_dates_from: Whether to prefer past or future dates.
        timezone: Timezone for date calculations.
    """
    fiscal_year: FiscalYearConfig = field(default_factory=FiscalYearConfig)
    default_date_format: str = "YYYY-MM-DD"
    prefer_dates_from: str = "past"
    timezone: str = "UTC"


@dataclass
class ParsedDateRange:
    """
    Result of parsing a date reference.
    
    Attributes:
        original_text: The original text that was parsed.
        reference_type: Type of date reference detected.
        start_date: Start of the date range.
        end_date: End of the date range (same as start for single dates).
        confidence: Confidence score for the parse (0.0 to 1.0).
        is_fiscal: Whether this is a fiscal date reference.
        metadata: Additional parsing metadata.
    """
    original_text: str
    reference_type: DateReferenceType
    start_date: datetime
    end_date: datetime
    confidence: float
    is_fiscal: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Validate parsed date range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")
        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be after end_date")


class DateParser:
    """
    Enhanced date parser with natural language and fiscal year support.
    
    Parses various date references from natural language queries:
    - Relative: "last quarter", "YTD", "past 6 months", "this week"
    - Absolute: "January 2024", "Q1 2024", "2024-01-15"
    - Fiscal: "FY2024", "fiscal Q1", "fiscal year to date"
    
    All dependencies are injected via constructor following DIP.
    
    Supports Requirements 33.1, 33.4, 33.6.
    """
    
    # Patterns for relative date references
    RELATIVE_PATTERNS: list[dict[str, Any]] = [
        {
            "pattern": r"\b(last|past|previous)\s+(\d+)\s+(day|week|month|quarter|year)s?\b",
            "type": DateReferenceType.RELATIVE_DATE,
            "confidence": 0.95,
        },
        {
            "pattern": r"\b(this|current)\s+(day|week|month|quarter|year)\b",
            "type": DateReferenceType.RELATIVE_DATE,
            "confidence": 0.95,
        },
        {
            "pattern": r"\b(next)\s+(\d+)?\s*(day|week|month|quarter|year)s?\b",
            "type": DateReferenceType.RELATIVE_DATE,
            "confidence": 0.90,
        },
        {
            "pattern": r"\byesterday\b",
            "type": DateReferenceType.RELATIVE_DATE,
            "confidence": 0.98,
        },
        {
            "pattern": r"\btoday\b",
            "type": DateReferenceType.RELATIVE_DATE,
            "confidence": 0.98,
        },
        {
            "pattern": r"\btomorrow\b",
            "type": DateReferenceType.RELATIVE_DATE,
            "confidence": 0.98,
        },
    ]
    
    # Patterns for period-to-date references
    PTD_PATTERNS: list[dict[str, Any]] = [
        {
            "pattern": r"\b(ytd|year[\s-]?to[\s-]?date)\b",
            "type": DateReferenceType.YTD,
            "confidence": 0.98,
        },
        {
            "pattern": r"\b(mtd|month[\s-]?to[\s-]?date)\b",
            "type": DateReferenceType.MTD,
            "confidence": 0.98,
        },
        {
            "pattern": r"\b(qtd|quarter[\s-]?to[\s-]?date)\b",
            "type": DateReferenceType.QTD,
            "confidence": 0.98,
        },
    ]
    
    # Patterns for quarter references
    QUARTER_PATTERNS: list[dict[str, Any]] = [
        {
            "pattern": r"\b(Q[1-4])\s*(\d{4})\b",
            "type": DateReferenceType.QUARTER,
            "confidence": 0.95,
        },
        {
            "pattern": r"\b(\d{4})\s*(Q[1-4])\b",
            "type": DateReferenceType.QUARTER,
            "confidence": 0.95,
        },
        {
            "pattern": r"\b(first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter\s*(\d{4})?\b",
            "type": DateReferenceType.QUARTER,
            "confidence": 0.90,
        },
    ]
    
    # Patterns for fiscal references
    FISCAL_PATTERNS: list[dict[str, Any]] = [
        {
            "pattern": r"\b(fy|fiscal\s*year)\s*(\d{4})\b",
            "type": DateReferenceType.FISCAL_YEAR,
            "confidence": 0.95,
        },
        {
            "pattern": r"\bfiscal\s*(Q[1-4])\s*(\d{4})?\b",
            "type": DateReferenceType.FISCAL_QUARTER,
            "confidence": 0.95,
        },
        {
            "pattern": r"\bfiscal\s+(ytd|year[\s-]?to[\s-]?date)\b",
            "type": DateReferenceType.YTD,
            "confidence": 0.95,
        },
    ]
    
    # Patterns for absolute date formats
    DATE_FORMAT_PATTERNS: list[dict[str, Any]] = [
        {
            "pattern": r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b",
            "type": DateReferenceType.ABSOLUTE_DATE,
            "format": "YYYY-MM-DD",
            "confidence": 0.95,
        },
        {
            "pattern": r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b",
            "type": DateReferenceType.ABSOLUTE_DATE,
            "format": "MM/DD/YYYY",
            "confidence": 0.85,
        },
        {
            "pattern": r"\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2})?,?\s*(\d{4})\b",
            "type": DateReferenceType.MONTH,
            "confidence": 0.92,
        },
        {
            "pattern": r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{4})\b",
            "type": DateReferenceType.ABSOLUTE_DATE,
            "confidence": 0.92,
        },
    ]
    
    # Quarter name mappings
    QUARTER_NAMES: dict[str, int] = {
        "first": 1, "1st": 1, "q1": 1,
        "second": 2, "2nd": 2, "q2": 2,
        "third": 3, "3rd": 3, "q3": 3,
        "fourth": 4, "4th": 4, "q4": 4,
    }
    
    def __init__(self, config: Optional[DateParserConfig] = None) -> None:
        """
        Initialize DateParser with configuration.
        
        Args:
            config: Parser configuration. Uses defaults if not provided.
        """
        self._config = config or DateParserConfig()
        logger.info(
            f"DateParser initialized with fiscal year starting "
            f"{self._config.fiscal_year.start_month}/{self._config.fiscal_year.start_day}"
        )
    
    def parse(
        self,
        text: str,
        reference_date: Optional[datetime] = None,
    ) -> list[ParsedDateRange]:
        """
        Parse all date references from text.
        
        Args:
            text: Text to parse for date references.
            reference_date: Reference date for relative calculations.
                Defaults to current datetime.
        
        Returns:
            List of parsed date ranges sorted by confidence.
        
        Raises:
            ValueError: If text is empty.
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        ref_date = reference_date or datetime.now()
        results: list[ParsedDateRange] = []
        
        # Parse fiscal references first (they take precedence)
        results.extend(self._parse_fiscal_references(text, ref_date))
        
        # Parse period-to-date references
        results.extend(self._parse_ptd_references(text, ref_date))
        
        # Parse quarter references
        results.extend(self._parse_quarter_references(text, ref_date))
        
        # Parse relative date references
        results.extend(self._parse_relative_references(text, ref_date))
        
        # Parse absolute date formats
        results.extend(self._parse_absolute_dates(text, ref_date))
        
        # Remove duplicates and sort by confidence
        unique_results = self._deduplicate_results(results)
        unique_results.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.debug(f"Parsed {len(unique_results)} date references from: {text[:50]}...")
        return unique_results
    
    def parse_single(
        self,
        text: str,
        reference_date: Optional[datetime] = None,
    ) -> Optional[ParsedDateRange]:
        """
        Parse and return the highest confidence date reference.
        
        Args:
            text: Text to parse.
            reference_date: Reference date for relative calculations.
        
        Returns:
            Highest confidence ParsedDateRange or None if no dates found.
        """
        results = self.parse(text, reference_date)
        return results[0] if results else None

    
    def _parse_fiscal_references(
        self,
        text: str,
        ref_date: datetime,
    ) -> list[ParsedDateRange]:
        """Parse fiscal year and quarter references."""
        results: list[ParsedDateRange] = []
        text_lower = text.lower()
        
        for pattern_info in self.FISCAL_PATTERNS:
            pattern = pattern_info["pattern"]
            ref_type = pattern_info["type"]
            confidence = pattern_info["confidence"]
            
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                try:
                    parsed = self._resolve_fiscal_match(match, ref_type, ref_date)
                    if parsed:
                        results.append(ParsedDateRange(
                            original_text=match.group(0),
                            reference_type=ref_type,
                            start_date=parsed["start"],
                            end_date=parsed["end"],
                            confidence=confidence,
                            is_fiscal=True,
                            metadata=parsed.get("metadata", {}),
                        ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse fiscal reference '{match.group(0)}': {e}")
        
        return results
    
    def _resolve_fiscal_match(
        self,
        match: re.Match,
        ref_type: DateReferenceType,
        ref_date: datetime,
    ) -> Optional[dict[str, Any]]:
        """Resolve a fiscal pattern match to date range."""
        groups = match.groups()
        fy_config = self._config.fiscal_year
        
        if ref_type == DateReferenceType.FISCAL_YEAR:
            # Extract year from groups
            year = None
            for g in groups:
                if g and g.isdigit() and len(g) == 4:
                    year = int(g)
                    break
            
            if not year:
                year = self._get_current_fiscal_year(ref_date)
            
            start, end = self._get_fiscal_year_range(year)
            return {"start": start, "end": end, "metadata": {"fiscal_year": year}}
        
        elif ref_type == DateReferenceType.FISCAL_QUARTER:
            # Extract quarter and optional year
            quarter = None
            year = None
            
            for g in groups:
                if g:
                    g_lower = g.lower()
                    if g_lower.startswith("q") and len(g_lower) == 2:
                        quarter = int(g_lower[1])
                    elif g.isdigit() and len(g) == 4:
                        year = int(g)
            
            if not quarter:
                return None
            
            if not year:
                year = self._get_current_fiscal_year(ref_date)
            
            start, end = self._get_fiscal_quarter_range(year, quarter)
            return {
                "start": start,
                "end": end,
                "metadata": {"fiscal_year": year, "fiscal_quarter": quarter},
            }
        
        return None
    
    def _parse_ptd_references(
        self,
        text: str,
        ref_date: datetime,
    ) -> list[ParsedDateRange]:
        """Parse period-to-date references (YTD, MTD, QTD)."""
        results: list[ParsedDateRange] = []
        text_lower = text.lower()
        
        for pattern_info in self.PTD_PATTERNS:
            pattern = pattern_info["pattern"]
            ref_type = pattern_info["type"]
            confidence = pattern_info["confidence"]
            
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                try:
                    start, end = self._resolve_ptd_range(ref_type, ref_date)
                    results.append(ParsedDateRange(
                        original_text=match.group(0),
                        reference_type=ref_type,
                        start_date=start,
                        end_date=end,
                        confidence=confidence,
                        is_fiscal=False,
                        metadata={"reference_date": ref_date.isoformat()},
                    ))
                except ValueError as e:
                    logger.debug(f"Failed to parse PTD reference '{match.group(0)}': {e}")
        
        return results
    
    def _resolve_ptd_range(
        self,
        ref_type: DateReferenceType,
        ref_date: datetime,
    ) -> tuple[datetime, datetime]:
        """Resolve period-to-date to date range."""
        if ref_type == DateReferenceType.YTD:
            start = datetime(ref_date.year, 1, 1)
            return start, ref_date
        
        elif ref_type == DateReferenceType.MTD:
            start = datetime(ref_date.year, ref_date.month, 1)
            return start, ref_date
        
        elif ref_type == DateReferenceType.QTD:
            quarter = (ref_date.month - 1) // 3 + 1
            quarter_start_month = (quarter - 1) * 3 + 1
            start = datetime(ref_date.year, quarter_start_month, 1)
            return start, ref_date
        
        raise ValueError(f"Unknown PTD type: {ref_type}")
    
    def _parse_quarter_references(
        self,
        text: str,
        ref_date: datetime,
    ) -> list[ParsedDateRange]:
        """Parse calendar quarter references."""
        results: list[ParsedDateRange] = []
        
        for pattern_info in self.QUARTER_PATTERNS:
            pattern = pattern_info["pattern"]
            confidence = pattern_info["confidence"]
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    parsed = self._resolve_quarter_match(match, ref_date)
                    if parsed:
                        results.append(ParsedDateRange(
                            original_text=match.group(0),
                            reference_type=DateReferenceType.QUARTER,
                            start_date=parsed["start"],
                            end_date=parsed["end"],
                            confidence=confidence,
                            is_fiscal=False,
                            metadata=parsed.get("metadata", {}),
                        ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse quarter '{match.group(0)}': {e}")
        
        return results
    
    def _resolve_quarter_match(
        self,
        match: re.Match,
        ref_date: datetime,
    ) -> Optional[dict[str, Any]]:
        """Resolve a quarter pattern match to date range."""
        groups = match.groups()
        quarter = None
        year = None
        
        for g in groups:
            if not g:
                continue
            g_lower = g.lower()
            
            # Check for quarter number
            if g_lower in self.QUARTER_NAMES:
                quarter = self.QUARTER_NAMES[g_lower]
            elif g_lower.startswith("q") and len(g_lower) == 2 and g_lower[1].isdigit():
                quarter = int(g_lower[1])
            # Check for year
            elif g.isdigit() and len(g) == 4:
                year = int(g)
        
        if not quarter:
            return None
        
        if not year:
            year = ref_date.year
        
        start, end = self._get_calendar_quarter_range(year, quarter)
        return {"start": start, "end": end, "metadata": {"year": year, "quarter": quarter}}

    
    def _parse_relative_references(
        self,
        text: str,
        ref_date: datetime,
    ) -> list[ParsedDateRange]:
        """Parse relative date references."""
        results: list[ParsedDateRange] = []
        text_lower = text.lower()
        
        for pattern_info in self.RELATIVE_PATTERNS:
            pattern = pattern_info["pattern"]
            ref_type = pattern_info["type"]
            confidence = pattern_info["confidence"]
            
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                try:
                    parsed = self._resolve_relative_match(match, ref_date)
                    if parsed:
                        results.append(ParsedDateRange(
                            original_text=match.group(0),
                            reference_type=ref_type,
                            start_date=parsed["start"],
                            end_date=parsed["end"],
                            confidence=confidence,
                            is_fiscal=False,
                            metadata=parsed.get("metadata", {}),
                        ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse relative date '{match.group(0)}': {e}")
        
        return results
    
    def _resolve_relative_match(
        self,
        match: re.Match,
        ref_date: datetime,
    ) -> Optional[dict[str, Any]]:
        """Resolve a relative date pattern match."""
        text = match.group(0).lower()
        
        # Handle simple keywords
        if text == "yesterday":
            d = ref_date.replace(hour=0, minute=0, second=0, microsecond=0)
            from datetime import timedelta
            start = d - timedelta(days=1)
            end = start.replace(hour=23, minute=59, second=59)
            return {"start": start, "end": end}
        
        if text == "today":
            start = ref_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = ref_date.replace(hour=23, minute=59, second=59)
            return {"start": start, "end": end}
        
        if text == "tomorrow":
            from datetime import timedelta
            d = ref_date.replace(hour=0, minute=0, second=0, microsecond=0)
            start = d + timedelta(days=1)
            end = start.replace(hour=23, minute=59, second=59)
            return {"start": start, "end": end}
        
        # Use dateparser for complex relative references
        parsed = dateparser.parse(
            text,
            settings={
                "PREFER_DATES_FROM": self._config.prefer_dates_from,
                "RELATIVE_BASE": ref_date,
            }
        )
        
        if parsed:
            # Determine the range based on the unit mentioned
            start, end = self._expand_relative_to_range(text, parsed, ref_date)
            return {"start": start, "end": end, "metadata": {"parsed_by": "dateparser"}}
        
        return None
    
    def _expand_relative_to_range(
        self,
        text: str,
        parsed_date: datetime,
        ref_date: datetime,
    ) -> tuple[datetime, datetime]:
        """Expand a relative date to a full range."""
        from datetime import timedelta
        from calendar import monthrange
        
        text_lower = text.lower()
        
        # Determine the unit and expand accordingly
        if "year" in text_lower:
            if "last" in text_lower or "past" in text_lower or "previous" in text_lower:
                # Extract number if present
                num_match = re.search(r"(\d+)", text_lower)
                num = int(num_match.group(1)) if num_match else 1
                end = ref_date
                start = datetime(ref_date.year - num, ref_date.month, ref_date.day)
            else:
                start = datetime(parsed_date.year, 1, 1)
                end = datetime(parsed_date.year, 12, 31, 23, 59, 59)
            return start, end
        
        if "quarter" in text_lower:
            quarter = (parsed_date.month - 1) // 3 + 1
            start, end = self._get_calendar_quarter_range(parsed_date.year, quarter)
            return start, end
        
        if "month" in text_lower:
            if "last" in text_lower or "past" in text_lower or "previous" in text_lower:
                num_match = re.search(r"(\d+)", text_lower)
                num = int(num_match.group(1)) if num_match else 1
                end = ref_date
                # Go back num months
                year = ref_date.year
                month = ref_date.month - num
                while month <= 0:
                    month += 12
                    year -= 1
                start = datetime(year, month, ref_date.day)
            else:
                _, last_day = monthrange(parsed_date.year, parsed_date.month)
                start = datetime(parsed_date.year, parsed_date.month, 1)
                end = datetime(parsed_date.year, parsed_date.month, last_day, 23, 59, 59)
            return start, end
        
        if "week" in text_lower:
            # Start of week (Monday)
            days_since_monday = parsed_date.weekday()
            start = parsed_date - timedelta(days=days_since_monday)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return start, end
        
        if "day" in text_lower:
            if "last" in text_lower or "past" in text_lower or "previous" in text_lower:
                num_match = re.search(r"(\d+)", text_lower)
                num = int(num_match.group(1)) if num_match else 1
                end = ref_date
                start = ref_date - timedelta(days=num)
            else:
                start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end = parsed_date.replace(hour=23, minute=59, second=59)
            return start, end
        
        # Default: single day
        start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = parsed_date.replace(hour=23, minute=59, second=59)
        return start, end
    
    def _parse_absolute_dates(
        self,
        text: str,
        ref_date: datetime,
    ) -> list[ParsedDateRange]:
        """Parse absolute date formats."""
        results: list[ParsedDateRange] = []
        
        for pattern_info in self.DATE_FORMAT_PATTERNS:
            pattern = pattern_info["pattern"]
            ref_type = pattern_info["type"]
            confidence = pattern_info["confidence"]
            
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    parsed = dateparser.parse(
                        match.group(0),
                        settings={
                            "PREFER_DATES_FROM": self._config.prefer_dates_from,
                            "RELATIVE_BASE": ref_date,
                        }
                    )
                    
                    if parsed:
                        # Expand to range based on type
                        start, end = self._expand_absolute_to_range(
                            match.group(0), parsed, ref_type
                        )
                        results.append(ParsedDateRange(
                            original_text=match.group(0),
                            reference_type=ref_type,
                            start_date=start,
                            end_date=end,
                            confidence=confidence,
                            is_fiscal=False,
                            metadata={"format": pattern_info.get("format", "auto")},
                        ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"Failed to parse date '{match.group(0)}': {e}")
        
        return results
    
    def _expand_absolute_to_range(
        self,
        text: str,
        parsed_date: datetime,
        ref_type: DateReferenceType,
    ) -> tuple[datetime, datetime]:
        """Expand an absolute date to a range based on type."""
        from calendar import monthrange
        
        if ref_type == DateReferenceType.MONTH:
            _, last_day = monthrange(parsed_date.year, parsed_date.month)
            start = datetime(parsed_date.year, parsed_date.month, 1)
            end = datetime(parsed_date.year, parsed_date.month, last_day, 23, 59, 59)
            return start, end
        
        if ref_type == DateReferenceType.YEAR:
            start = datetime(parsed_date.year, 1, 1)
            end = datetime(parsed_date.year, 12, 31, 23, 59, 59)
            return start, end
        
        # Single day
        start = parsed_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = parsed_date.replace(hour=23, minute=59, second=59)
        return start, end

    
    def _get_fiscal_year_range(self, fiscal_year: int) -> tuple[datetime, datetime]:
        """
        Get the date range for a fiscal year.
        
        Args:
            fiscal_year: The fiscal year number.
        
        Returns:
            Tuple of (start_date, end_date) for the fiscal year.
        """
        fy_config = self._config.fiscal_year
        
        # Fiscal year starts in the previous calendar year if start_month > 1
        if fy_config.start_month == 1 and fy_config.start_day == 1:
            # Calendar year aligned
            start = datetime(fiscal_year, 1, 1)
            end = datetime(fiscal_year, 12, 31, 23, 59, 59)
        else:
            # Fiscal year spans two calendar years
            start = datetime(fiscal_year - 1, fy_config.start_month, fy_config.start_day)
            
            # End is one day before the next fiscal year starts
            end_year = fiscal_year
            end_month = fy_config.start_month
            end_day = fy_config.start_day - 1
            
            if end_day < 1:
                end_month -= 1
                if end_month < 1:
                    end_month = 12
                    end_year -= 1
                from calendar import monthrange
                _, end_day = monthrange(end_year, end_month)
            
            end = datetime(end_year, end_month, end_day, 23, 59, 59)
        
        return start, end
    
    def _get_fiscal_quarter_range(
        self,
        fiscal_year: int,
        quarter: int,
    ) -> tuple[datetime, datetime]:
        """
        Get the date range for a fiscal quarter.
        
        Args:
            fiscal_year: The fiscal year number.
            quarter: Quarter number (1-4).
        
        Returns:
            Tuple of (start_date, end_date) for the fiscal quarter.
        """
        if not 1 <= quarter <= 4:
            raise ValueError(f"Quarter must be 1-4, got {quarter}")
        
        fy_start, fy_end = self._get_fiscal_year_range(fiscal_year)
        
        # Calculate quarter boundaries
        from datetime import timedelta
        from calendar import monthrange
        
        # Each quarter is approximately 3 months
        quarter_months = 3
        
        # Calculate start month offset
        start_offset_months = (quarter - 1) * quarter_months
        
        # Calculate start date
        start_month = fy_start.month + start_offset_months
        start_year = fy_start.year
        
        while start_month > 12:
            start_month -= 12
            start_year += 1
        
        start = datetime(start_year, start_month, 1)
        
        # Calculate end date (3 months later, minus 1 day)
        end_month = start_month + quarter_months - 1
        end_year = start_year
        
        while end_month > 12:
            end_month -= 12
            end_year += 1
        
        _, last_day = monthrange(end_year, end_month)
        end = datetime(end_year, end_month, last_day, 23, 59, 59)
        
        return start, end
    
    def _get_calendar_quarter_range(
        self,
        year: int,
        quarter: int,
    ) -> tuple[datetime, datetime]:
        """
        Get the date range for a calendar quarter.
        
        Args:
            year: Calendar year.
            quarter: Quarter number (1-4).
        
        Returns:
            Tuple of (start_date, end_date) for the quarter.
        """
        if not 1 <= quarter <= 4:
            raise ValueError(f"Quarter must be 1-4, got {quarter}")
        
        from calendar import monthrange
        
        start_month = (quarter - 1) * 3 + 1
        end_month = quarter * 3
        
        start = datetime(year, start_month, 1)
        _, last_day = monthrange(year, end_month)
        end = datetime(year, end_month, last_day, 23, 59, 59)
        
        return start, end
    
    def _get_current_fiscal_year(self, ref_date: datetime) -> int:
        """
        Determine the current fiscal year based on reference date.
        
        Args:
            ref_date: Reference date.
        
        Returns:
            Current fiscal year number.
        """
        fy_config = self._config.fiscal_year
        
        # If we're before the fiscal year start, we're in the previous FY
        if fy_config.start_month == 1 and fy_config.start_day == 1:
            return ref_date.year
        
        fy_start_this_year = datetime(
            ref_date.year, fy_config.start_month, fy_config.start_day
        )
        
        if ref_date >= fy_start_this_year:
            return ref_date.year + 1
        else:
            return ref_date.year
    
    def _deduplicate_results(
        self,
        results: list[ParsedDateRange],
    ) -> list[ParsedDateRange]:
        """Remove duplicate date ranges, keeping highest confidence."""
        seen: dict[str, ParsedDateRange] = {}
        
        for result in results:
            key = f"{result.start_date.date()}_{result.end_date.date()}"
            
            if key not in seen or result.confidence > seen[key].confidence:
                seen[key] = result
        
        return list(seen.values())
    
    def format_date_range(
        self,
        date_range: ParsedDateRange,
        format_str: str = "%Y-%m-%d",
    ) -> str:
        """
        Format a parsed date range as a human-readable string.
        
        Args:
            date_range: The parsed date range.
            format_str: strftime format string.
        
        Returns:
            Formatted date range string.
        """
        if date_range.start_date.date() == date_range.end_date.date():
            return date_range.start_date.strftime(format_str)
        
        return (
            f"{date_range.start_date.strftime(format_str)} to "
            f"{date_range.end_date.strftime(format_str)}"
        )
