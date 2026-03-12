"""
Excel Chunker

Implements sliding-window chunking for large sheets so that every row
range is represented in the vector index, not just the first 5 rows.
"""

import logging
from typing import List, Dict, Any

from src.models.domain_models import SheetData

logger = logging.getLogger(__name__)


class ExcelChunker:
    """
    Splits a sheet into overlapping row-window chunks for embedding.

    Instead of sampling only the first N rows, this creates multiple
    overlapping text chunks that cover the entire sheet, ensuring
    data in later rows is discoverable via semantic search.
    """

    def __init__(self, chunk_size: int = 50, overlap: int = 5):
        """
        Args:
            chunk_size: Number of rows per chunk
            overlap: Number of rows shared between consecutive chunks
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_sheet(self, sheet: SheetData, file_name: str) -> List[Dict[str, Any]]:
        """
        Produce overlapping text chunks for a sheet.

        Args:
            sheet: SheetData domain object
            file_name: Name of the parent file (for context)

        Returns:
            List of dicts with keys: text, start_row, end_row, chunk_index
        """
        rows = sheet.rows or []
        if not rows:
            return []

        chunks = []
        step = max(1, self.chunk_size - self.overlap)
        chunk_index = 0

        for start in range(0, len(rows), step):
            end = min(start + self.chunk_size, len(rows))
            window = rows[start:end]

            text = self._rows_to_text(
                rows=window,
                headers=sheet.headers,
                file_name=file_name,
                sheet_name=sheet.sheet_name,
                start_row=start,
                end_row=end - 1
            )

            chunks.append({
                "text": text,
                "start_row": start,
                "end_row": end - 1,
                "chunk_index": chunk_index
            })
            chunk_index += 1

            if end >= len(rows):
                break

        logger.debug(
            f"Chunked sheet '{sheet.sheet_name}' ({len(rows)} rows) "
            f"into {len(chunks)} chunks (size={self.chunk_size}, overlap={self.overlap})"
        )
        return chunks

    def _rows_to_text(
        self,
        rows: List[Dict[str, Any]],
        headers: List[str],
        file_name: str,
        sheet_name: str,
        start_row: int,
        end_row: int
    ) -> str:
        """Convert a row window to an embeddable text string."""
        parts = [
            f"File: {file_name}",
            f"Sheet: {sheet_name}",
            f"Rows {start_row + 1}-{end_row + 1}:",
        ]

        if headers:
            parts.append(f"Columns: {', '.join(headers)}")

        for row in rows:
            row_str = ", ".join(
                f"{k}: {v}" for k, v in row.items() if v is not None
            )
            if row_str:
                parts.append(f"  {row_str}")

        return "\n".join(parts)
