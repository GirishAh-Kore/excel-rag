"""
Sheet Aligner for aligning data across multiple Excel sheets.

This module provides the SheetAligner class that matches sheets by name,
identifies common columns, and aligns rows for comparison.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from Levenshtein import distance as levenshtein_distance

from src.models.domain_models import SheetData, AlignedData

logger = logging.getLogger(__name__)


class SheetAligner:
    """
    Aligns sheets from different files for comparison.
    
    This class handles matching sheets by name, identifying common columns,
    finding key columns for row alignment, and handling structural differences.
    """
    
    def __init__(
        self,
        sheet_name_threshold: float = 0.8,
        column_name_threshold: float = 0.85,
        max_levenshtein_distance: int = 3
    ):
        """
        Initialize the SheetAligner.
        
        Args:
            sheet_name_threshold: Fuzzy matching threshold for sheet names (0-1)
            column_name_threshold: Fuzzy matching threshold for column names (0-1)
            max_levenshtein_distance: Maximum Levenshtein distance for fuzzy matching
        """
        self.sheet_name_threshold = sheet_name_threshold
        self.column_name_threshold = column_name_threshold
        self.max_levenshtein_distance = max_levenshtein_distance
        
        logger.info("SheetAligner initialized")
    
    def align_sheets(
        self,
        sheets: List[SheetData],
        file_ids: List[str]
    ) -> AlignedData:
        """
        Align multiple sheets for comparison.
        
        Args:
            sheets: List of SheetData objects to align
            file_ids: Corresponding file IDs for each sheet
        
        Returns:
            AlignedData structure with aligned columns and rows
        """
        if not sheets or not file_ids:
            return AlignedData(
                common_columns=[],
                file_data={},
                missing_columns={}
            )
        
        if len(sheets) != len(file_ids):
            raise ValueError("Number of sheets must match number of file_ids")
        
        logger.info(f"Aligning {len(sheets)} sheets")
        
        # Step 1: Match sheets by name (group similar sheets together)
        sheet_groups = self._group_sheets_by_name(sheets, file_ids)
        
        # Step 2: For each group, identify common columns
        aligned_data = self._align_sheet_group(sheet_groups)
        
        # Step 3: Calculate alignment quality
        quality_score = self._calculate_alignment_quality(aligned_data)
        logger.info(f"Alignment quality score: {quality_score:.2f}")
        
        # Step 4: Log warnings for structural differences
        self._log_structural_warnings(aligned_data)
        
        return aligned_data
    
    def _group_sheets_by_name(
        self,
        sheets: List[SheetData],
        file_ids: List[str]
    ) -> Dict[str, List[Tuple[SheetData, str]]]:
        """
        Group sheets by similar names using fuzzy matching.
        
        Args:
            sheets: List of sheets to group
            file_ids: Corresponding file IDs
        
        Returns:
            Dictionary mapping group name to list of (sheet, file_id) tuples
        """
        groups: Dict[str, List[Tuple[SheetData, str]]] = {}
        
        for sheet, file_id in zip(sheets, file_ids):
            # Find matching group or create new one
            matched_group = None
            
            for group_name in groups.keys():
                if self._sheets_match(sheet.sheet_name, group_name):
                    matched_group = group_name
                    break
            
            if matched_group:
                groups[matched_group].append((sheet, file_id))
            else:
                # Create new group with this sheet's name
                groups[sheet.sheet_name] = [(sheet, file_id)]
        
        logger.info(f"Grouped sheets into {len(groups)} groups")
        return groups
    
    def _sheets_match(self, name1: str, name2: str) -> bool:
        """
        Check if two sheet names match using fuzzy matching.
        
        Args:
            name1: First sheet name
            name2: Second sheet name
        
        Returns:
            True if names match within threshold
        """
        # Exact match
        if name1.lower() == name2.lower():
            return True
        
        # Levenshtein distance check
        dist = levenshtein_distance(name1.lower(), name2.lower())
        if dist <= self.max_levenshtein_distance:
            return True
        
        # Similarity ratio check
        max_len = max(len(name1), len(name2))
        if max_len == 0:
            return True
        
        similarity = 1 - (dist / max_len)
        return similarity >= self.sheet_name_threshold
    
    def _align_sheet_group(
        self,
        sheet_groups: Dict[str, List[Tuple[SheetData, str]]]
    ) -> AlignedData:
        """
        Align sheets within groups and create AlignedData structure.
        
        Args:
            sheet_groups: Groups of similar sheets
        
        Returns:
            AlignedData with aligned columns and rows
        """
        # For simplicity, we'll align the largest group
        # In production, we might handle multiple groups differently
        largest_group = max(sheet_groups.values(), key=len) if sheet_groups else []
        
        if not largest_group:
            return AlignedData(
                common_columns=[],
                file_data={},
                missing_columns={}
            )
        
        # Extract sheets and file_ids from the group
        sheets = [item[0] for item in largest_group]
        file_ids = [item[1] for item in largest_group]
        
        # Step 1: Identify common columns
        common_columns = self._find_common_columns(sheets)
        
        # Step 2: Identify missing columns per file
        missing_columns = self._find_missing_columns(sheets, file_ids, common_columns)
        
        # Step 3: Align rows based on key columns
        file_data = self._align_rows(sheets, file_ids, common_columns)
        
        return AlignedData(
            common_columns=common_columns,
            file_data=file_data,
            missing_columns=missing_columns
        )
    
    def _find_common_columns(self, sheets: List[SheetData]) -> List[str]:
        """
        Find columns that are common across all sheets.
        
        Args:
            sheets: List of sheets to analyze
        
        Returns:
            List of common column names
        """
        if not sheets:
            return []
        
        # Start with columns from first sheet
        common_columns = set(sheets[0].headers)
        
        # Intersect with columns from other sheets using fuzzy matching
        for sheet in sheets[1:]:
            matched_columns = set()
            
            for col in common_columns:
                for sheet_col in sheet.headers:
                    if self._columns_match(col, sheet_col):
                        matched_columns.add(col)
                        break
            
            common_columns = matched_columns
        
        result = sorted(list(common_columns))
        logger.info(f"Found {len(result)} common columns: {result}")
        return result
    
    def _columns_match(self, col1: str, col2: str) -> bool:
        """
        Check if two column names match using fuzzy matching.
        
        Args:
            col1: First column name
            col2: Second column name
        
        Returns:
            True if columns match within threshold
        """
        # Exact match (case-insensitive)
        if col1.lower() == col2.lower():
            return True
        
        # Levenshtein distance check
        dist = levenshtein_distance(col1.lower(), col2.lower())
        max_len = max(len(col1), len(col2))
        
        if max_len == 0:
            return True
        
        similarity = 1 - (dist / max_len)
        return similarity >= self.column_name_threshold
    
    def _find_missing_columns(
        self,
        sheets: List[SheetData],
        file_ids: List[str],
        common_columns: List[str]
    ) -> Dict[str, List[str]]:
        """
        Identify columns missing from each file.
        
        Args:
            sheets: List of sheets
            file_ids: Corresponding file IDs
            common_columns: List of common columns
        
        Returns:
            Dictionary mapping file_id to list of missing column names
        """
        missing_columns = {}
        
        for sheet, file_id in zip(sheets, file_ids):
            missing = []
            
            for col in common_columns:
                # Check if this column exists in the sheet (with fuzzy matching)
                found = False
                for sheet_col in sheet.headers:
                    if self._columns_match(col, sheet_col):
                        found = True
                        break
                
                if not found:
                    missing.append(col)
            
            if missing:
                missing_columns[file_id] = missing
                logger.warning(f"File {file_id} is missing columns: {missing}")
        
        return missing_columns
    
    def _align_rows(
        self,
        sheets: List[SheetData],
        file_ids: List[str],
        common_columns: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Align rows across sheets based on key columns.
        
        Args:
            sheets: List of sheets to align
            file_ids: Corresponding file IDs
            common_columns: Common columns to include
        
        Returns:
            Dictionary mapping file_id to list of row data
        """
        file_data = {}
        
        # Identify key columns for alignment (dates, IDs, categories)
        key_columns = self._identify_key_columns(sheets, common_columns)
        logger.info(f"Using key columns for alignment: {key_columns}")
        
        for sheet, file_id in zip(sheets, file_ids):
            # Extract rows with only common columns
            aligned_rows = []
            
            for row in sheet.rows:
                aligned_row = {}
                
                for col in common_columns:
                    # Find matching column in sheet (with fuzzy matching)
                    value = None
                    for sheet_col in sheet.headers:
                        if self._columns_match(col, sheet_col):
                            value = row.get(sheet_col)
                            break
                    
                    aligned_row[col] = value
                
                aligned_rows.append(aligned_row)
            
            file_data[file_id] = aligned_rows
        
        # If key columns exist, sort rows by key columns for better alignment
        if key_columns:
            for file_id in file_data:
                file_data[file_id] = self._sort_by_key_columns(
                    file_data[file_id],
                    key_columns
                )
        
        return file_data
    
    def _identify_key_columns(
        self,
        sheets: List[SheetData],
        common_columns: List[str]
    ) -> List[str]:
        """
        Identify key columns for row alignment (dates, IDs, categories).
        
        Args:
            sheets: List of sheets
            common_columns: Common columns to consider
        
        Returns:
            List of key column names
        """
        key_columns = []
        
        # Heuristics for identifying key columns
        key_indicators = [
            'id', 'date', 'month', 'year', 'quarter', 'week',
            'category', 'name', 'region', 'department', 'product'
        ]
        
        for col in common_columns:
            col_lower = col.lower()
            
            # Check if column name contains key indicators
            if any(indicator in col_lower for indicator in key_indicators):
                key_columns.append(col)
        
        return key_columns
    
    def _sort_by_key_columns(
        self,
        rows: List[Dict[str, Any]],
        key_columns: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Sort rows by key columns for better alignment.
        
        Args:
            rows: List of row dictionaries
            key_columns: Columns to sort by
        
        Returns:
            Sorted list of rows
        """
        try:
            # Sort by key columns in order
            sorted_rows = sorted(
                rows,
                key=lambda row: tuple(
                    str(row.get(col, '')) for col in key_columns
                )
            )
            return sorted_rows
        except Exception as e:
            logger.warning(f"Failed to sort rows by key columns: {str(e)}")
            return rows
    
    def _calculate_alignment_quality(self, aligned_data: AlignedData) -> float:
        """
        Calculate quality score for the alignment.
        
        Args:
            aligned_data: Aligned data structure
        
        Returns:
            Quality score between 0 and 1
        """
        if not aligned_data.file_data:
            return 0.0
        
        # Calculate based on:
        # 1. Number of common columns vs total unique columns
        # 2. Number of files with missing columns
        
        total_files = len(aligned_data.file_data)
        files_with_missing = len(aligned_data.missing_columns)
        
        # Quality decreases with more missing columns
        completeness_score = 1.0 - (files_with_missing / total_files) if total_files > 0 else 0.0
        
        return completeness_score
    
    def _log_structural_warnings(self, aligned_data: AlignedData) -> None:
        """
        Log warnings about structural differences in aligned data.
        
        Args:
            aligned_data: Aligned data structure
        """
        if aligned_data.missing_columns:
            logger.warning(
                f"Structural differences detected: {len(aligned_data.missing_columns)} "
                f"files have missing columns"
            )
            
            for file_id, missing_cols in aligned_data.missing_columns.items():
                logger.warning(f"File {file_id} missing: {', '.join(missing_cols)}")
        
        # Check for row count differences
        if aligned_data.file_data:
            row_counts = {
                file_id: len(rows)
                for file_id, rows in aligned_data.file_data.items()
            }
            
            if len(set(row_counts.values())) > 1:
                logger.warning(
                    f"Row count differences detected: {row_counts}"
                )
