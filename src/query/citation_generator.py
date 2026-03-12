"""
Citation generator for creating source citations in answers.

This module generates consistent citations for data sources, linking specific
data points to their Excel file origins with file name, sheet name, and cell range.
"""

from typing import Dict, List, Optional, Tuple
from src.models.domain_models import RetrievedData


class Citation:
    """Represents a single citation."""
    
    def __init__(
        self,
        citation_id: int,
        file_name: str,
        sheet_name: str,
        cell_range: str,
        file_path: Optional[str] = None
    ):
        """
        Initialize a citation.
        
        Args:
            citation_id: Unique citation number
            file_name: Name of the Excel file
            sheet_name: Name of the sheet
            cell_range: Cell range (e.g., "B10" or "A1:C5")
            file_path: Optional full file path
        """
        self.citation_id = citation_id
        self.file_name = file_name
        self.sheet_name = sheet_name
        self.cell_range = cell_range
        self.file_path = file_path
    
    def format_inline(self, style: str = "superscript") -> str:
        """
        Format citation for inline use.
        
        Args:
            style: Citation style ('superscript', 'bracket', 'parenthesis')
            
        Returns:
            Formatted inline citation
        """
        if style == "superscript":
            return f"[{self.citation_id}]"
        elif style == "bracket":
            return f"[{self.citation_id}]"
        elif style == "parenthesis":
            return f"({self.citation_id})"
        else:
            return f"[{self.citation_id}]"
    
    def format_full(self, language: str = "en") -> str:
        """
        Format full citation for reference list.
        
        Args:
            language: Language code ('en' or 'th')
            
        Returns:
            Formatted full citation
        """
        if language == "th":
            return f"[{self.citation_id}] แหล่งที่มา: {self.file_name}, ชีต: {self.sheet_name}, เซลล์: {self.cell_range}"
        else:
            return f"[{self.citation_id}] Source: {self.file_name}, Sheet: {self.sheet_name}, Cell: {self.cell_range}"
    
    def __str__(self) -> str:
        """String representation."""
        return self.format_full()


class CitationGenerator:
    """
    Generates and manages citations for data sources.
    
    Creates consistent citations linking data points to their Excel file sources,
    with support for inline references and citation lists.
    """
    
    def __init__(self, language: str = "en"):
        """
        Initialize the citation generator.
        
        Args:
            language: Language code ('en' or 'th')
        """
        self.language = language
        self.citations: List[Citation] = []
        self.citation_map: Dict[str, int] = {}  # Maps source key to citation ID
    
    def add_citation(
        self,
        file_name: str,
        sheet_name: str,
        cell_range: str,
        file_path: Optional[str] = None
    ) -> Citation:
        """
        Add a citation and return it.
        
        Args:
            file_name: Name of the Excel file
            sheet_name: Name of the sheet
            cell_range: Cell range
            file_path: Optional full file path
            
        Returns:
            Citation object
        """
        # Create a unique key for this source
        source_key = f"{file_name}::{sheet_name}::{cell_range}"
        
        # Check if citation already exists
        if source_key in self.citation_map:
            citation_id = self.citation_map[source_key]
            return self.citations[citation_id - 1]
        
        # Create new citation
        citation_id = len(self.citations) + 1
        citation = Citation(citation_id, file_name, sheet_name, cell_range, file_path)
        
        self.citations.append(citation)
        self.citation_map[source_key] = citation_id
        
        return citation
    
    def add_from_retrieved_data(self, data: RetrievedData) -> Citation:
        """
        Add a citation from RetrievedData object.
        
        Args:
            data: Retrieved data object
            
        Returns:
            Citation object
        """
        return self.add_citation(
            file_name=data.file_name,
            sheet_name=data.sheet_name,
            cell_range=data.cell_range,
            file_path=data.file_path
        )
    
    def get_inline_citation(
        self,
        file_name: str,
        sheet_name: str,
        cell_range: str,
        style: str = "superscript"
    ) -> str:
        """
        Get inline citation for a specific source.
        
        Args:
            file_name: Name of the Excel file
            sheet_name: Name of the sheet
            cell_range: Cell range
            style: Citation style
            
        Returns:
            Inline citation string
        """
        citation = self.add_citation(file_name, sheet_name, cell_range)
        return citation.format_inline(style)
    
    def generate_citation_list(self, format_style: str = "numbered") -> str:
        """
        Generate a formatted list of all citations.
        
        Args:
            format_style: Format style ('numbered', 'bulleted')
            
        Returns:
            Formatted citation list
        """
        if not self.citations:
            return ""
        
        lines = []
        
        # Add header
        if self.language == "th":
            lines.append("\n**แหล่งอ้างอิง:**\n")
        else:
            lines.append("\n**Sources:**\n")
        
        # Add each citation
        for citation in self.citations:
            if format_style == "bulleted":
                lines.append(f"- {citation.format_full(self.language)}")
            else:  # numbered
                lines.append(citation.format_full(self.language))
        
        return "\n".join(lines)
    
    def annotate_answer(
        self,
        answer: str,
        data_sources: List[RetrievedData],
        auto_annotate: bool = True
    ) -> Tuple[str, str]:
        """
        Annotate an answer with citations.
        
        Args:
            answer: The answer text
            data_sources: List of data sources used
            auto_annotate: Whether to automatically add citations to the answer
            
        Returns:
            Tuple of (annotated_answer, citation_list)
        """
        # Add citations for all data sources
        citations_added = []
        for data in data_sources:
            citation = self.add_from_retrieved_data(data)
            citations_added.append(citation)
        
        annotated_answer = answer
        
        # Auto-annotate if requested
        if auto_annotate and citations_added:
            # Add citation at the end of the answer
            inline_citations = ", ".join([c.format_inline() for c in citations_added])
            annotated_answer = f"{answer} {inline_citations}"
        
        # Generate citation list
        citation_list = self.generate_citation_list()
        
        return annotated_answer, citation_list
    
    def create_detailed_citation(
        self,
        file_name: str,
        sheet_name: str,
        cell_range: str,
        data_description: Optional[str] = None,
        file_path: Optional[str] = None
    ) -> str:
        """
        Create a detailed citation with additional context.
        
        Args:
            file_name: Name of the Excel file
            sheet_name: Name of the sheet
            cell_range: Cell range
            data_description: Optional description of the data
            file_path: Optional full file path
            
        Returns:
            Detailed citation string
        """
        citation = self.add_citation(file_name, sheet_name, cell_range, file_path)
        
        parts = [citation.format_full(self.language)]
        
        if file_path:
            if self.language == "th":
                parts.append(f"  ตำแหน่ง: {file_path}")
            else:
                parts.append(f"  Location: {file_path}")
        
        if data_description:
            if self.language == "th":
                parts.append(f"  ข้อมูล: {data_description}")
            else:
                parts.append(f"  Data: {data_description}")
        
        return "\n".join(parts)
    
    def format_multiple_sources(
        self,
        sources: List[RetrievedData],
        group_by_file: bool = True
    ) -> str:
        """
        Format multiple sources in a structured way.
        
        Args:
            sources: List of retrieved data sources
            group_by_file: Whether to group citations by file
            
        Returns:
            Formatted sources string
        """
        if not sources:
            return ""
        
        if group_by_file:
            return self._format_grouped_sources(sources)
        else:
            return self._format_flat_sources(sources)
    
    def _format_grouped_sources(self, sources: List[RetrievedData]) -> str:
        """Format sources grouped by file."""
        # Group by file
        file_groups: Dict[str, List[RetrievedData]] = {}
        for source in sources:
            if source.file_name not in file_groups:
                file_groups[source.file_name] = []
            file_groups[source.file_name].append(source)
        
        lines = []
        
        if self.language == "th":
            lines.append("\n**แหล่งข้อมูล:**\n")
        else:
            lines.append("\n**Data Sources:**\n")
        
        for file_name, file_sources in file_groups.items():
            lines.append(f"\n**{file_name}**")
            
            # Group by sheet within file
            sheet_groups: Dict[str, List[str]] = {}
            for source in file_sources:
                if source.sheet_name not in sheet_groups:
                    sheet_groups[source.sheet_name] = []
                sheet_groups[source.sheet_name].append(source.cell_range)
            
            for sheet_name, cell_ranges in sheet_groups.items():
                ranges_str = ", ".join(cell_ranges)
                if self.language == "th":
                    lines.append(f"  - ชีต '{sheet_name}': เซลล์ {ranges_str}")
                else:
                    lines.append(f"  - Sheet '{sheet_name}': Cells {ranges_str}")
        
        return "\n".join(lines)
    
    def _format_flat_sources(self, sources: List[RetrievedData]) -> str:
        """Format sources in a flat list."""
        lines = []
        
        if self.language == "th":
            lines.append("\n**แหล่งข้อมูล:**\n")
        else:
            lines.append("\n**Data Sources:**\n")
        
        for source in sources:
            citation = self.add_from_retrieved_data(source)
            lines.append(f"- {citation.format_full(self.language)}")
        
        return "\n".join(lines)
    
    def clear(self):
        """Clear all citations."""
        self.citations.clear()
        self.citation_map.clear()
    
    def get_citation_count(self) -> int:
        """Get the number of unique citations."""
        return len(self.citations)
    
    def get_citation_by_id(self, citation_id: int) -> Optional[Citation]:
        """
        Get a citation by its ID.
        
        Args:
            citation_id: Citation ID (1-indexed)
            
        Returns:
            Citation object or None if not found
        """
        if 1 <= citation_id <= len(self.citations):
            return self.citations[citation_id - 1]
        return None
    
    def format_comparison_sources(
        self,
        files_compared: List[str],
        sheets_used: Dict[str, List[str]]
    ) -> str:
        """
        Format sources for comparison queries.
        
        Args:
            files_compared: List of file names compared
            sheets_used: Dictionary mapping file names to sheet names used
            
        Returns:
            Formatted comparison sources
        """
        lines = []
        
        if self.language == "th":
            lines.append("\n**ไฟล์ที่เปรียบเทียบ:**\n")
        else:
            lines.append("\n**Files Compared:**\n")
        
        for file_name in files_compared:
            sheets = sheets_used.get(file_name, [])
            if sheets:
                sheets_str = ", ".join(f"'{s}'" for s in sheets)
                if self.language == "th":
                    lines.append(f"- {file_name} (ชีต: {sheets_str})")
                else:
                    lines.append(f"- {file_name} (Sheets: {sheets_str})")
            else:
                lines.append(f"- {file_name}")
        
        return "\n".join(lines)
    
    def create_footnote_style_citations(
        self,
        answer: str,
        sources: List[RetrievedData]
    ) -> str:
        """
        Create answer with footnote-style citations.
        
        Args:
            answer: The answer text
            sources: List of data sources
            
        Returns:
            Answer with footnote citations appended
        """
        # Add citations
        for source in sources:
            self.add_from_retrieved_data(source)
        
        # Generate citation list
        citation_list = self.generate_citation_list()
        
        # Combine answer and citations
        if citation_list:
            return f"{answer}\n{citation_list}"
        return answer
