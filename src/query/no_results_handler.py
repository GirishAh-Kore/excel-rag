"""
Handler for queries that return no results.

This module provides helpful error messages and suggestions when no relevant
data is found, helping users refine their queries.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from src.models.domain_models import FileMetadata


@dataclass
class NoResultsResponse:
    """Response for queries with no results."""
    
    message: str
    reason: str
    suggestions: List[str]
    available_files: List[str]
    available_sheets: List[str]
    available_columns: List[str]
    search_criteria: Dict[str, any]
    relaxed_search_available: bool


class NoResultsHandler:
    """
    Handles queries that return no results.
    
    Generates helpful error messages, explains what was searched, and suggests
    query refinements based on indexed data.
    """
    
    def __init__(self, language: str = "en"):
        """
        Initialize the no results handler.
        
        Args:
            language: Language code ('en' or 'th')
        """
        self.language = language
    
    def handle_no_results(
        self,
        query: str,
        search_criteria: Dict[str, any],
        indexed_files: Optional[List[FileMetadata]] = None,
        indexed_sheets: Optional[List[str]] = None,
        indexed_columns: Optional[Set[str]] = None,
        min_similarity_threshold: float = 0.0
    ) -> NoResultsResponse:
        """
        Handle a query that returned no results.
        
        Args:
            query: The user's query
            search_criteria: Criteria used in the search
            indexed_files: List of indexed files
            indexed_sheets: List of indexed sheet names
            indexed_columns: Set of indexed column names
            min_similarity_threshold: Minimum similarity threshold used
            
        Returns:
            NoResultsResponse with message and suggestions
        """
        # Determine the reason for no results
        reason = self._determine_reason(search_criteria, min_similarity_threshold)
        
        # Generate main message
        message = self._generate_message(query, reason)
        
        # Generate suggestions
        suggestions = self._generate_suggestions(
            query,
            search_criteria,
            indexed_files,
            indexed_sheets,
            indexed_columns,
            min_similarity_threshold
        )
        
        # Extract available data
        available_files = self._extract_available_files(indexed_files)
        available_sheets = self._extract_available_sheets(indexed_sheets)
        available_columns = self._extract_available_columns(indexed_columns)
        
        # Check if relaxed search is available
        relaxed_available = min_similarity_threshold > 0.3
        
        return NoResultsResponse(
            message=message,
            reason=reason,
            suggestions=suggestions,
            available_files=available_files,
            available_sheets=available_sheets,
            available_columns=available_columns,
            search_criteria=search_criteria,
            relaxed_search_available=relaxed_available
        )
    
    def format_response(self, response: NoResultsResponse) -> str:
        """
        Format no results response for display.
        
        Args:
            response: NoResultsResponse object
            
        Returns:
            Formatted response string
        """
        lines = []
        
        # Main message
        lines.append(response.message)
        lines.append("")
        
        # Reason
        if self.language == "th":
            lines.append(f"**สาเหตุ:** {response.reason}")
        else:
            lines.append(f"**Reason:** {response.reason}")
        lines.append("")
        
        # Suggestions
        if response.suggestions:
            if self.language == "th":
                lines.append("**คำแนะนำ:**")
            else:
                lines.append("**Suggestions:**")
            
            for suggestion in response.suggestions:
                lines.append(f"- {suggestion}")
            lines.append("")
        
        # Available data
        if response.available_files:
            if self.language == "th":
                lines.append(f"**ไฟล์ที่มี:** {len(response.available_files)} ไฟล์")
            else:
                lines.append(f"**Available Files:** {len(response.available_files)} files")
            
            # Show sample files
            sample_files = response.available_files[:5]
            for file in sample_files:
                lines.append(f"  - {file}")
            
            if len(response.available_files) > 5:
                remaining = len(response.available_files) - 5
                if self.language == "th":
                    lines.append(f"  ... และอีก {remaining} ไฟล์")
                else:
                    lines.append(f"  ... and {remaining} more")
            lines.append("")
        
        # Relaxed search option
        if response.relaxed_search_available:
            if self.language == "th":
                lines.append("**ต้องการค้นหาด้วยเกณฑ์ที่ผ่อนปรนกว่านี้หรือไม่?**")
            else:
                lines.append("**Would you like to search with relaxed criteria?**")
        
        return "\n".join(lines)
    
    def _determine_reason(
        self,
        search_criteria: Dict[str, any],
        min_similarity_threshold: float
    ) -> str:
        """Determine the reason for no results."""
        reasons = []
        
        # Check if filters were too restrictive
        if search_criteria.get("date_filter"):
            if self.language == "th":
                reasons.append("ตัวกรองวันที่อาจจำกัดเกินไป")
            else:
                reasons.append("Date filter may be too restrictive")
        
        if search_criteria.get("file_name_filter"):
            if self.language == "th":
                reasons.append("ตัวกรองชื่อไฟล์อาจจำกัดเกินไป")
            else:
                reasons.append("File name filter may be too restrictive")
        
        if min_similarity_threshold > 0.7:
            if self.language == "th":
                reasons.append("เกณฑ์ความคล้ายคลึงสูงเกินไป")
            else:
                reasons.append("Similarity threshold is too high")
        
        # Default reason
        if not reasons:
            if self.language == "th":
                reasons.append("ไม่พบข้อมูลที่ตรงกับคำถาม")
            else:
                reasons.append("No data matches the query")
        
        return "; ".join(reasons)
    
    def _generate_message(self, query: str, reason: str) -> str:
        """Generate the main no results message."""
        if self.language == "th":
            return f"ขออภัย ไม่พบข้อมูลสำหรับคำถาม: \"{query}\""
        else:
            return f"Sorry, no data found for query: \"{query}\""
    
    def _generate_suggestions(
        self,
        query: str,
        search_criteria: Dict[str, any],
        indexed_files: Optional[List[FileMetadata]],
        indexed_sheets: Optional[List[str]],
        indexed_columns: Optional[Set[str]],
        min_similarity_threshold: float
    ) -> List[str]:
        """Generate suggestions for refining the query."""
        suggestions = []
        
        # Suggest removing filters
        if search_criteria.get("date_filter"):
            if self.language == "th":
                suggestions.append("ลองค้นหาโดยไม่ระบุวันที่")
            else:
                suggestions.append("Try searching without date restrictions")
        
        if search_criteria.get("file_name_filter"):
            if self.language == "th":
                suggestions.append("ลองค้นหาในไฟล์ทั้งหมด")
            else:
                suggestions.append("Try searching across all files")
        
        # Suggest lowering threshold
        if min_similarity_threshold > 0.5:
            if self.language == "th":
                suggestions.append("ลองค้นหาด้วยเกณฑ์ที่ผ่อนปรนกว่า")
            else:
                suggestions.append("Try searching with relaxed criteria")
        
        # Suggest using different terms
        if self.language == "th":
            suggestions.append("ลองใช้คำค้นหาที่แตกต่างหรือเฉพาะเจาะจงมากขึ้น")
        else:
            suggestions.append("Try using different or more specific search terms")
        
        # Suggest checking available data
        if indexed_files:
            if self.language == "th":
                suggestions.append("ตรวจสอบรายชื่อไฟล์ที่มีด้านล่าง")
            else:
                suggestions.append("Check the list of available files below")
        
        # Suggest checking column names
        if indexed_columns:
            sample_columns = list(indexed_columns)[:10]
            columns_str = ", ".join(sample_columns)
            if self.language == "th":
                suggestions.append(f"คอลัมน์ที่มี: {columns_str}")
            else:
                suggestions.append(f"Available columns include: {columns_str}")
        
        # Suggest checking sheet names
        if indexed_sheets:
            sample_sheets = indexed_sheets[:10]
            sheets_str = ", ".join(sample_sheets)
            if self.language == "th":
                suggestions.append(f"ชีตที่มี: {sheets_str}")
            else:
                suggestions.append(f"Available sheets include: {sheets_str}")
        
        return suggestions
    
    def _extract_available_files(
        self,
        indexed_files: Optional[List[FileMetadata]]
    ) -> List[str]:
        """Extract list of available file names."""
        if not indexed_files:
            return []
        
        return [f.name for f in indexed_files]
    
    def _extract_available_sheets(
        self,
        indexed_sheets: Optional[List[str]]
    ) -> List[str]:
        """Extract list of available sheet names."""
        if not indexed_sheets:
            return []
        
        # Get unique sheet names
        unique_sheets = list(set(indexed_sheets))
        return sorted(unique_sheets)
    
    def _extract_available_columns(
        self,
        indexed_columns: Optional[Set[str]]
    ) -> List[str]:
        """Extract list of available column names."""
        if not indexed_columns:
            return []
        
        return sorted(list(indexed_columns))
    
    def suggest_similar_queries(
        self,
        query: str,
        indexed_files: Optional[List[FileMetadata]] = None
    ) -> List[str]:
        """
        Suggest similar queries based on indexed data.
        
        Args:
            query: The original query
            indexed_files: List of indexed files
            
        Returns:
            List of suggested queries
        """
        suggestions = []
        
        if not indexed_files:
            return suggestions
        
        # Extract common patterns from file names
        file_patterns = self._extract_file_patterns(indexed_files)
        
        # Generate query suggestions
        for pattern in file_patterns[:3]:
            if self.language == "th":
                suggestions.append(f"ข้อมูลจาก {pattern}")
            else:
                suggestions.append(f"Data from {pattern}")
        
        return suggestions
    
    def _extract_file_patterns(
        self,
        indexed_files: List[FileMetadata]
    ) -> List[str]:
        """Extract common patterns from file names."""
        patterns = set()
        
        for file in indexed_files:
            # Extract words from file name
            name_parts = file.name.replace("_", " ").replace("-", " ").split()
            
            # Add significant words (longer than 3 characters)
            for part in name_parts:
                if len(part) > 3 and not part.isdigit():
                    patterns.add(part)
        
        return list(patterns)
    
    def create_relaxed_search_message(self) -> str:
        """Create message for offering relaxed search."""
        if self.language == "th":
            return """ไม่พบผลลัพธ์ที่ตรงกับเกณฑ์การค้นหา

คุณต้องการให้:
1. ลดเกณฑ์ความคล้ายคลึง (อาจได้ผลลัพธ์ที่เกี่ยวข้องน้อยลง)
2. ขยายช่วงวันที่ (ถ้ามีการกรองวันที่)
3. ค้นหาในไฟล์ทั้งหมด (ไม่จำกัดชื่อไฟล์)

กรุณาเลือกหรือปรับคำค้นหาของคุณ"""
        else:
            return """No results found matching the search criteria.

Would you like to:
1. Lower the similarity threshold (may return less relevant results)
2. Expand the date range (if date filtering was applied)
3. Search across all files (remove file name restrictions)

Please choose an option or refine your query."""
    
    def explain_search_criteria(self, search_criteria: Dict[str, any]) -> str:
        """
        Explain what search criteria were used.
        
        Args:
            search_criteria: Search criteria dictionary
            
        Returns:
            Explanation string
        """
        lines = []
        
        if self.language == "th":
            lines.append("**เกณฑ์การค้นหาที่ใช้:**")
        else:
            lines.append("**Search Criteria Used:**")
        
        if search_criteria.get("query"):
            if self.language == "th":
                lines.append(f"- คำค้นหา: {search_criteria['query']}")
            else:
                lines.append(f"- Query: {search_criteria['query']}")
        
        if search_criteria.get("date_filter"):
            date_filter = search_criteria["date_filter"]
            if self.language == "th":
                lines.append(f"- ตัวกรองวันที่: {date_filter}")
            else:
                lines.append(f"- Date Filter: {date_filter}")
        
        if search_criteria.get("file_name_filter"):
            file_filter = search_criteria["file_name_filter"]
            if self.language == "th":
                lines.append(f"- ตัวกรองชื่อไฟล์: {file_filter}")
            else:
                lines.append(f"- File Name Filter: {file_filter}")
        
        if search_criteria.get("min_similarity"):
            min_sim = search_criteria["min_similarity"]
            if self.language == "th":
                lines.append(f"- ความคล้ายคลึงขั้นต่ำ: {min_sim:.2f}")
            else:
                lines.append(f"- Minimum Similarity: {min_sim:.2f}")
        
        if search_criteria.get("top_k"):
            top_k = search_criteria["top_k"]
            if self.language == "th":
                lines.append(f"- จำนวนผลลัพธ์สูงสุด: {top_k}")
            else:
                lines.append(f"- Maximum Results: {top_k}")
        
        return "\n".join(lines)
