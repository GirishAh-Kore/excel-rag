"""
Query Analyzer Module

Analyzes user queries to extract entities, dates, intent, and comparison types.
Uses LLM service to understand natural language queries and structure them
for downstream processing.
"""

import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

import dateparser
from pydantic import BaseModel, Field

from src.abstractions.llm_service import LLMService

logger = logging.getLogger(__name__)


class QueryAnalysis(BaseModel):
    """Structured analysis of a user query."""
    
    entities: List[str] = Field(
        default_factory=list,
        description="Key entities mentioned in query (e.g., 'expenses', 'revenue', 'sales')"
    )
    intent: str = Field(
        ...,
        description="Primary intent of the query (e.g., 'retrieve_value', 'compare', 'explain_formula', 'list_items')"
    )
    temporal_refs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Temporal references with parsed dates (e.g., [{'text': 'January', 'date': '2024-01-01'}])"
    )
    comparison_type: Optional[str] = Field(
        default=None,
        description="Type of comparison if applicable ('temporal', 'categorical', 'structural', None)"
    )
    is_comparison: bool = Field(
        default=False,
        description="Whether this is a comparison query"
    )
    data_types_requested: List[str] = Field(
        default_factory=list,
        description="Types of data being requested ('numbers', 'dates', 'text', 'formulas', 'charts', 'pivots')"
    )
    file_name_hints: List[str] = Field(
        default_factory=list,
        description="File name patterns or hints from query"
    )
    path_patterns: List[str] = Field(
        default_factory=list,
        description="Path patterns mentioned in query"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in the analysis"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "entities": ["expenses", "January"],
                "intent": "retrieve_value",
                "temporal_refs": [{"text": "January", "date": "2024-01-01", "type": "month"}],
                "comparison_type": None,
                "is_comparison": False,
                "data_types_requested": ["numbers"],
                "file_name_hints": ["expenses"],
                "path_patterns": [],
                "confidence": 0.95
            }
        }


class QueryAnalyzer:
    """
    Analyzes user queries to extract structured information.
    
    Uses LLM service to understand natural language and extract:
    - Entities (what the user is asking about)
    - Intent (what they want to do)
    - Temporal references (dates, months, quarters)
    - Comparison indicators
    - Data types requested
    - File/path hints
    """
    
    # Comparison keywords for detection
    COMPARISON_KEYWORDS = [
        "compare", "comparison", "difference", "vs", "versus",
        "between", "change from", "changed", "increase", "decrease",
        "higher", "lower", "more than", "less than", "against"
    ]
    
    # Data type keywords
    DATA_TYPE_KEYWORDS = {
        "numbers": ["total", "sum", "amount", "value", "count", "average", "number"],
        "dates": ["date", "when", "time", "day", "month", "year"],
        "text": ["name", "description", "label", "category", "type"],
        "formulas": ["formula", "calculation", "how is", "calculated", "compute"],
        "charts": ["chart", "graph", "visualization", "plot"],
        "pivots": ["pivot", "summary", "breakdown", "grouped by"]
    }
    
    def __init__(self, llm_service: LLMService):
        """
        Initialize QueryAnalyzer.
        
        Args:
            llm_service: LLM service for natural language understanding
        """
        self.llm_service = llm_service
        logger.info(f"QueryAnalyzer initialized with LLM: {llm_service.get_model_name()}")
    
    def analyze(self, query: str) -> QueryAnalysis:
        """
        Analyze a user query and extract structured information.
        
        Args:
            query: Natural language query from user
            
        Returns:
            QueryAnalysis with extracted information
        """
        logger.info(f"Analyzing query: {query}")
        
        try:
            # Quick keyword-based detection for comparison
            is_comparison = self._detect_comparison_keywords(query)
            
            # Parse temporal references
            temporal_refs = self._parse_temporal_references(query)
            
            # Detect data types requested
            data_types = self._detect_data_types(query)
            
            # Extract file/path hints
            file_hints, path_patterns = self._extract_file_hints(query)
            
            # Use LLM for deeper analysis
            llm_analysis = self._llm_analyze(query, is_comparison, temporal_refs)
            
            # Combine results
            analysis = QueryAnalysis(
                entities=llm_analysis.get("entities", []),
                intent=llm_analysis.get("intent", "retrieve_value"),
                temporal_refs=temporal_refs,
                comparison_type=llm_analysis.get("comparison_type") if is_comparison else None,
                is_comparison=is_comparison,
                data_types_requested=data_types,
                file_name_hints=file_hints,
                path_patterns=path_patterns,
                confidence=llm_analysis.get("confidence", 0.8)
            )
            
            logger.info(f"Query analysis complete: intent={analysis.intent}, is_comparison={analysis.is_comparison}")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing query: {e}", exc_info=True)
            # Return basic analysis on error
            return QueryAnalysis(
                entities=[],
                intent="retrieve_value",
                temporal_refs=[],
                is_comparison=False,
                data_types_requested=["numbers"],
                file_name_hints=[],
                path_patterns=[],
                confidence=0.5
            )
    
    def _detect_comparison_keywords(self, query: str) -> bool:
        """
        Detect if query contains comparison keywords.
        
        Args:
            query: User query
            
        Returns:
            True if comparison keywords found
        """
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.COMPARISON_KEYWORDS)
    
    def _parse_temporal_references(self, query: str) -> List[Dict[str, Any]]:
        """
        Parse temporal references from query using dateparser.
        
        Args:
            query: User query
            
        Returns:
            List of temporal references with parsed dates
        """
        temporal_refs = []
        
        # Common temporal patterns
        patterns = [
            r'\b(last|this|next)\s+(month|year|quarter|week)\b',
            r'\b(Q[1-4])\s*(\d{4})?\b',
            r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s*(\d{4})?\b',
            r'\b(\d{4})\b',
            r'\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b',
            r'\b(\d{1,2})-(\d{1,2})-(\d{2,4})\b'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, query, re.IGNORECASE)
            for match in matches:
                text = match.group(0)
                
                # Try to parse the date
                parsed_date = dateparser.parse(
                    text,
                    settings={
                        'PREFER_DATES_FROM': 'past',
                        'RELATIVE_BASE': datetime.now()
                    }
                )
                
                if parsed_date:
                    temporal_refs.append({
                        "text": text,
                        "date": parsed_date.isoformat(),
                        "type": self._classify_temporal_type(text)
                    })
        
        return temporal_refs
    
    def _classify_temporal_type(self, text: str) -> str:
        """
        Classify the type of temporal reference.
        
        Args:
            text: Temporal text
            
        Returns:
            Type classification ('month', 'year', 'quarter', 'date', 'relative')
        """
        text_lower = text.lower()
        
        if re.match(r'q[1-4]', text_lower):
            return "quarter"
        elif any(month in text_lower for month in [
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december"
        ]):
            return "month"
        elif re.match(r'\d{4}', text):
            return "year"
        elif "last" in text_lower or "this" in text_lower or "next" in text_lower:
            return "relative"
        else:
            return "date"
    
    def _detect_data_types(self, query: str) -> List[str]:
        """
        Detect what types of data are being requested.
        
        Args:
            query: User query
            
        Returns:
            List of data types
        """
        query_lower = query.lower()
        detected_types = []
        
        for data_type, keywords in self.DATA_TYPE_KEYWORDS.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_types.append(data_type)
        
        # Default to numbers if nothing detected
        if not detected_types:
            detected_types = ["numbers"]
        
        return detected_types
    
    def _extract_file_hints(self, query: str) -> tuple[List[str], List[str]]:
        """
        Extract file name hints and path patterns from query.
        
        Args:
            query: User query
            
        Returns:
            Tuple of (file_hints, path_patterns)
        """
        file_hints = []
        path_patterns = []
        
        # Look for quoted strings (often file names)
        quoted_strings = re.findall(r'"([^"]+)"', query)
        quoted_strings.extend(re.findall(r"'([^']+)'", query))
        
        for quoted in quoted_strings:
            if "/" in quoted or "\\" in quoted:
                path_patterns.append(quoted)
            else:
                file_hints.append(quoted)
        
        # Look for common file-related phrases
        file_patterns = [
            r'in\s+(?:the\s+)?(\w+)\s+file',
            r'from\s+(?:the\s+)?(\w+)\s+file',
            r'(\w+)\.xlsx?',
            r'file\s+named\s+(\w+)',
            r'file\s+called\s+(\w+)'
        ]
        
        for pattern in file_patterns:
            matches = re.finditer(pattern, query, re.IGNORECASE)
            for match in matches:
                file_hints.append(match.group(1))
        
        return file_hints, path_patterns
    
    def _llm_analyze(
        self,
        query: str,
        is_comparison: bool,
        temporal_refs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to perform deeper query analysis.
        
        Args:
            query: User query
            is_comparison: Whether comparison was detected
            temporal_refs: Parsed temporal references
            
        Returns:
            Dictionary with LLM analysis results
        """
        system_prompt = """You are a query analyzer for an Excel file RAG system.
Analyze the user's query and extract structured information.

Return a JSON object with:
- entities: List of key entities/concepts mentioned (e.g., ["expenses", "revenue"])
- intent: Primary intent (one of: "retrieve_value", "compare", "explain_formula", "list_items", "summarize", "find_file")
- comparison_type: If comparison, specify type ("temporal", "categorical", "structural", or null)
- confidence: Confidence score 0.0-1.0

Be concise and focus on the core information needed to answer the query."""

        user_prompt = f"""Query: "{query}"

Is comparison detected: {is_comparison}
Temporal references found: {len(temporal_refs)}

Analyze this query and return the structured information as JSON."""

        try:
            result = self.llm_service.generate_structured(
                prompt=user_prompt,
                response_schema={
                    "type": "object",
                    "properties": {
                        "entities": {"type": "array", "items": {"type": "string"}},
                        "intent": {"type": "string"},
                        "comparison_type": {"type": ["string", "null"]},
                        "confidence": {"type": "number"}
                    },
                    "required": ["entities", "intent", "confidence"]
                },
                system_prompt=system_prompt
            )
            
            return result
            
        except Exception as e:
            logger.warning(f"LLM analysis failed, using fallback: {e}")
            # Fallback to basic analysis
            return {
                "entities": [],
                "intent": "compare" if is_comparison else "retrieve_value",
                "comparison_type": "temporal" if is_comparison and temporal_refs else None,
                "confidence": 0.6
            }
