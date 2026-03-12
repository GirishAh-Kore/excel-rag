"""
Date Parser Module

Extracts and parses dates from file names and paths using regex patterns.
Matches extracted dates against query temporal references.
"""

import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

import dateparser

logger = logging.getLogger(__name__)


class ParsedDate(BaseModel):
    """A date parsed from a file name or path."""
    
    text: str = Field(..., description="Original text that was parsed")
    date: datetime = Field(..., description="Parsed datetime object")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in parse")
    format_type: str = Field(..., description="Type of date format detected")
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Jan2024",
                "date": "2024-01-01T00:00:00",
                "confidence": 0.95,
                "format_type": "month_year"
            }
        }


class DateParser:
    """
    Parses dates from file names and paths.
    
    Supports formats:
    - YYYY-MM-DD (2024-01-15)
    - MM-DD-YYYY (01-15-2024)
    - YYYY_MM_DD (2024_01_15)
    - Month YYYY (January 2024, Jan2024)
    - Q1 2024, Q2 2024, etc.
    - YYYYMMDD (20240115)
    - Relative dates (last month, this year, yesterday)
    """
    
    # Date format patterns with their confidence scores
    DATE_PATTERNS = [
        # ISO format: YYYY-MM-DD
        {
            "pattern": r'\b(\d{4})[-_/](\d{1,2})[-_/](\d{1,2})\b',
            "format_type": "iso_date",
            "confidence": 0.95
        },
        # US format: MM-DD-YYYY
        {
            "pattern": r'\b(\d{1,2})[-_/](\d{1,2})[-_/](\d{4})\b',
            "format_type": "us_date",
            "confidence": 0.90
        },
        # Compact: YYYYMMDD
        {
            "pattern": r'\b(\d{8})\b',
            "format_type": "compact_date",
            "confidence": 0.85
        },
        # Month Year: January 2024, Jan2024, Jan_2024
        {
            "pattern": r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[-_\s]*(\d{4})\b',
            "format_type": "month_year",
            "confidence": 0.90
        },
        # Quarter: Q1 2024, Q1_2024
        {
            "pattern": r'\b(Q[1-4])[-_\s]*(\d{4})\b',
            "format_type": "quarter",
            "confidence": 0.90
        },
        # Year only: 2024
        {
            "pattern": r'\b(20\d{2})\b',
            "format_type": "year",
            "confidence": 0.70
        },
        # Month only: January, Jan
        {
            "pattern": r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b',
            "format_type": "month",
            "confidence": 0.60
        }
    ]
    
    def __init__(self):
        """Initialize DateParser."""
        logger.info("DateParser initialized")
    
    def parse_dates_from_filename(self, filename: str) -> List[ParsedDate]:
        """
        Parse all dates from a filename or path.
        
        Args:
            filename: File name or path to parse
            
        Returns:
            List of parsed dates sorted by confidence
        """
        parsed_dates = []
        
        for pattern_info in self.DATE_PATTERNS:
            pattern = pattern_info["pattern"]
            format_type = pattern_info["format_type"]
            confidence = pattern_info["confidence"]
            
            matches = re.finditer(pattern, filename, re.IGNORECASE)
            
            for match in matches:
                text = match.group(0)
                
                # Try to parse the date
                parsed_date = self._parse_date_text(
                    text,
                    format_type,
                    confidence
                )
                
                if parsed_date:
                    parsed_dates.append(parsed_date)
        
        # Sort by confidence descending
        parsed_dates.sort(key=lambda x: x.confidence, reverse=True)
        
        # Remove duplicates (keep highest confidence)
        unique_dates = []
        seen_dates = set()
        
        for pd in parsed_dates:
            date_key = pd.date.strftime("%Y-%m-%d")
            if date_key not in seen_dates:
                unique_dates.append(pd)
                seen_dates.add(date_key)
        
        logger.debug(f"Parsed {len(unique_dates)} dates from: {filename}")
        return unique_dates
    
    def _parse_date_text(
        self,
        text: str,
        format_type: str,
        confidence: float
    ) -> Optional[ParsedDate]:
        """
        Parse date text using dateparser.
        
        Args:
            text: Text to parse
            format_type: Type of format detected
            confidence: Base confidence score
            
        Returns:
            ParsedDate or None if parsing fails
        """
        try:
            # Use dateparser for flexible parsing
            parsed = dateparser.parse(
                text,
                settings={
                    'PREFER_DATES_FROM': 'past',
                    'RELATIVE_BASE': datetime.now()
                }
            )
            
            if parsed:
                return ParsedDate(
                    text=text,
                    date=parsed,
                    confidence=confidence,
                    format_type=format_type
                )
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to parse date '{text}': {e}")
            return None
    
    def match_dates(
        self,
        parsed_date: ParsedDate,
        temporal_ref: Dict[str, Any]
    ) -> float:
        """
        Calculate match score between parsed date and temporal reference.
        
        Args:
            parsed_date: Date parsed from file name
            temporal_ref: Temporal reference from query
            
        Returns:
            Match score (0-1)
        """
        try:
            # Parse temporal reference date
            ref_date_str = temporal_ref.get("date")
            if not ref_date_str:
                return 0.0
            
            if isinstance(ref_date_str, str):
                ref_date = datetime.fromisoformat(ref_date_str.replace('Z', '+00:00'))
            else:
                ref_date = ref_date_str
            
            # Get temporal type
            temporal_type = temporal_ref.get("type", "date")
            
            # Match based on type
            if temporal_type == "year":
                # Match if same year
                if parsed_date.date.year == ref_date.year:
                    return 1.0
                return 0.0
            
            elif temporal_type == "month":
                # Match if same year and month
                if (parsed_date.date.year == ref_date.year and
                    parsed_date.date.month == ref_date.month):
                    return 1.0
                # Partial match if same month different year
                if parsed_date.date.month == ref_date.month:
                    return 0.5
                return 0.0
            
            elif temporal_type == "quarter":
                # Match if same year and quarter
                parsed_quarter = (parsed_date.date.month - 1) // 3 + 1
                ref_quarter = (ref_date.month - 1) // 3 + 1
                
                if (parsed_date.date.year == ref_date.year and
                    parsed_quarter == ref_quarter):
                    return 1.0
                return 0.0
            
            elif temporal_type == "date":
                # Match if same date
                if parsed_date.date.date() == ref_date.date():
                    return 1.0
                
                # Partial match if within 7 days
                days_diff = abs((parsed_date.date - ref_date).days)
                if days_diff <= 7:
                    return 1.0 - (days_diff / 7) * 0.5
                
                return 0.0
            
            elif temporal_type == "relative":
                # For relative dates, use fuzzy matching
                # This is handled by dateparser in the query analyzer
                # Here we just check if dates are close
                days_diff = abs((parsed_date.date - ref_date).days)
                if days_diff <= 30:
                    return 1.0 - (days_diff / 30) * 0.5
                return 0.0
            
            else:
                # Unknown type, use exact date matching
                if parsed_date.date.date() == ref_date.date():
                    return 1.0
                return 0.0
        
        except Exception as e:
            logger.warning(f"Error matching dates: {e}")
            return 0.0
    
    def extract_date_from_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Extract temporal references from query text.
        
        This is a simplified version - the main extraction is done
        by QueryAnalyzer. This method is for additional date extraction.
        
        Args:
            query: User query
            
        Returns:
            List of temporal references
        """
        temporal_refs = []
        
        for pattern_info in self.DATE_PATTERNS:
            pattern = pattern_info["pattern"]
            format_type = pattern_info["format_type"]
            
            matches = re.finditer(pattern, query, re.IGNORECASE)
            
            for match in matches:
                text = match.group(0)
                
                # Try to parse the date
                parsed = dateparser.parse(
                    text,
                    settings={
                        'PREFER_DATES_FROM': 'past',
                        'RELATIVE_BASE': datetime.now()
                    }
                )
                
                if parsed:
                    temporal_refs.append({
                        "text": text,
                        "date": parsed.isoformat(),
                        "type": format_type
                    })
        
        return temporal_refs
    
    def normalize_date_format(self, date: datetime, format_type: str) -> str:
        """
        Normalize date to a standard format based on type.
        
        Args:
            date: Datetime object
            format_type: Type of date format
            
        Returns:
            Formatted date string
        """
        if format_type == "year":
            return date.strftime("%Y")
        elif format_type in ["month", "month_year"]:
            return date.strftime("%B %Y")
        elif format_type == "quarter":
            quarter = (date.month - 1) // 3 + 1
            return f"Q{quarter} {date.year}"
        else:
            return date.strftime("%Y-%m-%d")
