"""
Metadata Storage Manager

This module manages storage of file and sheet metadata in SQLite database.
It handles inserting and updating file records, sheet records, pivot table records,
and chart records with MD5 checksum-based change detection.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.database.connection import DatabaseConnection
from src.models.domain_models import (
    FileMetadata,
    WorkbookData,
    SheetData,
    PivotTableData,
    ChartData,
    FileStatus
)


logger = logging.getLogger(__name__)


class MetadataStorageManager:
    """
    Manages storage of metadata in SQLite database.
    
    Features:
    - Store file metadata with MD5 checksums for change detection
    - Store sheet structure information
    - Store pivot table definitions
    - Store chart metadata
    - Update existing records instead of duplicating
    - Efficient batch operations
    """
    
    def __init__(self, db_connection: DatabaseConnection):
        """
        Initialize the metadata storage manager.
        
        Args:
            db_connection: Database connection
        """
        self.db_connection = db_connection
        logger.info("MetadataStorageManager initialized")
    
    def store_file_metadata(
        self,
        file_metadata: FileMetadata,
        status: FileStatus = FileStatus.INDEXED
    ) -> bool:
        """
        Store or update file metadata.
        
        Args:
            file_metadata: File metadata to store
            status: File status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    """
                    INSERT INTO files (
                        file_id, name, path, size, modified_time, md5_checksum, status, indexed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_id) DO UPDATE SET
                        name = excluded.name,
                        path = excluded.path,
                        size = excluded.size,
                        modified_time = excluded.modified_time,
                        md5_checksum = excluded.md5_checksum,
                        status = excluded.status,
                        indexed_at = excluded.indexed_at
                    """,
                    (
                        file_metadata.file_id,
                        file_metadata.name,
                        file_metadata.path,
                        file_metadata.size,
                        file_metadata.modified_time.isoformat(),
                        file_metadata.md5_checksum,
                        status.value,
                        datetime.now().isoformat() if status == FileStatus.INDEXED else None
                    )
                )
                
                conn.commit()
                logger.debug(f"Stored file metadata: {file_metadata.name}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing file metadata: {e}", exc_info=True)
            return False
    
    def store_workbook_metadata(self, workbook_data: WorkbookData) -> bool:
        """
        Store complete workbook metadata including sheets, pivots, and charts.
        
        Args:
            workbook_data: Workbook data to store
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Storing workbook metadata: {workbook_data.file_name}")
        
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # Store file metadata
                cursor.execute(
                    """
                    INSERT INTO files (
                        file_id, name, path, size, modified_time, md5_checksum, status, indexed_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(file_id) DO UPDATE SET
                        name = excluded.name,
                        path = excluded.path,
                        size = excluded.size,
                        modified_time = excluded.modified_time,
                        status = excluded.status,
                        indexed_at = excluded.indexed_at
                    """,
                    (
                        workbook_data.file_id,
                        workbook_data.file_name,
                        workbook_data.file_path,
                        0,  # Size not available in WorkbookData
                        workbook_data.modified_time.isoformat(),
                        "",  # MD5 not available in WorkbookData
                        FileStatus.INDEXED.value,
                        datetime.now().isoformat()
                    )
                )
                
                # Delete existing sheets for this file (to handle sheet deletions)
                cursor.execute("DELETE FROM sheets WHERE file_id = ?", (workbook_data.file_id,))
                
                # Store each sheet
                for sheet in workbook_data.sheets:
                    sheet_id = self._store_sheet_metadata(cursor, workbook_data.file_id, sheet)
                    
                    # Store pivot tables for this sheet
                    for pivot in sheet.pivot_tables:
                        self._store_pivot_metadata(cursor, sheet_id, pivot)
                    
                    # Store charts for this sheet
                    for chart in sheet.charts:
                        self._store_chart_metadata(cursor, sheet_id, chart)
                
                conn.commit()
                
                logger.info(
                    f"Stored workbook metadata: {workbook_data.file_name} "
                    f"({len(workbook_data.sheets)} sheets, "
                    f"{workbook_data.total_pivot_tables} pivots, "
                    f"{workbook_data.total_charts} charts)"
                )
                
                return True
                
        except Exception as e:
            logger.error(f"Error storing workbook metadata: {e}", exc_info=True)
            return False
    
    def _store_sheet_metadata(
        self,
        cursor,
        file_id: str,
        sheet: SheetData
    ) -> int:
        """
        Store sheet metadata and return the sheet ID.
        
        Args:
            cursor: Database cursor
            file_id: File ID
            sheet: Sheet data
            
        Returns:
            Sheet ID
        """
        cursor.execute(
            """
            INSERT INTO sheets (
                file_id, sheet_name, row_count, column_count, headers, data_types,
                has_pivot_tables, has_charts, pivot_count, chart_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                sheet.sheet_name,
                sheet.row_count,
                sheet.column_count,
                json.dumps(sheet.headers),
                json.dumps({k: v.value for k, v in sheet.data_types.items()}),
                sheet.has_pivot_tables,
                sheet.has_charts,
                len(sheet.pivot_tables),
                len(sheet.charts)
            )
        )
        
        return cursor.lastrowid
    
    def _store_pivot_metadata(
        self,
        cursor,
        sheet_id: int,
        pivot: PivotTableData
    ):
        """
        Store pivot table metadata.
        
        Args:
            cursor: Database cursor
            sheet_id: Sheet ID
            pivot: Pivot table data
        """
        cursor.execute(
            """
            INSERT INTO pivot_tables (
                sheet_id, name, location, source_range, row_fields, column_fields,
                data_fields, summary
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sheet_id,
                pivot.name,
                pivot.location,
                pivot.source_range,
                json.dumps(pivot.row_fields),
                json.dumps(pivot.column_fields),
                json.dumps(pivot.data_fields),
                pivot.summary
            )
        )
    
    def _store_chart_metadata(
        self,
        cursor,
        sheet_id: int,
        chart: ChartData
    ):
        """
        Store chart metadata.
        
        Args:
            cursor: Database cursor
            sheet_id: Sheet ID
            chart: Chart data
        """
        cursor.execute(
            """
            INSERT INTO charts (
                sheet_id, name, chart_type, title, source_range, summary
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                sheet_id,
                chart.name,
                chart.chart_type,
                chart.title,
                chart.source_range,
                chart.summary
            )
        )
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata by ID.
        
        Args:
            file_id: File ID
            
        Returns:
            File metadata dictionary or None
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM files WHERE file_id = ?",
                    (file_id,)
                )
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
                
        except Exception as e:
            logger.error(f"Error getting file metadata: {e}")
            return None
    
    def get_sheet_metadata(self, file_id: str) -> List[Dict[str, Any]]:
        """
        Get all sheet metadata for a file.
        
        Args:
            file_id: File ID
            
        Returns:
            List of sheet metadata dictionaries
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM sheets WHERE file_id = ?",
                    (file_id,)
                )
                
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting sheet metadata: {e}")
            return []
    
    def get_pivot_metadata(self, sheet_id: int) -> List[Dict[str, Any]]:
        """
        Get all pivot table metadata for a sheet.
        
        Args:
            sheet_id: Sheet ID
            
        Returns:
            List of pivot table metadata dictionaries
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM pivot_tables WHERE sheet_id = ?",
                    (sheet_id,)
                )
                
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting pivot metadata: {e}")
            return []
    
    def get_chart_metadata(self, sheet_id: int) -> List[Dict[str, Any]]:
        """
        Get all chart metadata for a sheet.
        
        Args:
            sheet_id: Sheet ID
            
        Returns:
            List of chart metadata dictionaries
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM charts WHERE sheet_id = ?",
                    (sheet_id,)
                )
                
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting chart metadata: {e}")
            return []
    
    def get_all_indexed_files(self) -> List[Dict[str, Any]]:
        """
        Get all indexed files.
        
        Returns:
            List of file metadata dictionaries
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM files WHERE status = ?",
                    (FileStatus.INDEXED.value,)
                )
                
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Error getting indexed files: {e}")
            return []
    
    def update_file_status(self, file_id: str, status: FileStatus) -> bool:
        """
        Update file status.
        
        Args:
            file_id: File ID
            status: New status
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE files SET status = ? WHERE file_id = ?",
                    (status.value, file_id)
                )
                conn.commit()
                
                logger.debug(f"Updated file status: {file_id} -> {status.value}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating file status: {e}")
            return False
    
    def delete_file_metadata(self, file_id: str) -> bool:
        """
        Delete all metadata for a file (cascades to sheets, pivots, charts).
        
        Args:
            file_id: File ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get sheet IDs for this file
                cursor.execute("SELECT id FROM sheets WHERE file_id = ?", (file_id,))
                sheet_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete pivot tables for these sheets
                for sheet_id in sheet_ids:
                    cursor.execute("DELETE FROM pivot_tables WHERE sheet_id = ?", (sheet_id,))
                    cursor.execute("DELETE FROM charts WHERE sheet_id = ?", (sheet_id,))
                
                # Delete sheets
                cursor.execute("DELETE FROM sheets WHERE file_id = ?", (file_id,))
                
                # Delete file
                cursor.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
                
                conn.commit()
                
                logger.info(f"Deleted metadata for file: {file_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting file metadata: {e}", exc_info=True)
            return False
    
    def get_indexing_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about indexed content.
        
        Returns:
            Dictionary with statistics
        """
        try:
            with self.db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count files by status
                cursor.execute(
                    "SELECT status, COUNT(*) FROM files GROUP BY status"
                )
                status_counts = dict(cursor.fetchall())
                
                # Count total sheets
                cursor.execute("SELECT COUNT(*) FROM sheets")
                total_sheets = cursor.fetchone()[0]
                
                # Count total pivot tables
                cursor.execute("SELECT COUNT(*) FROM pivot_tables")
                total_pivots = cursor.fetchone()[0]
                
                # Count total charts
                cursor.execute("SELECT COUNT(*) FROM charts")
                total_charts = cursor.fetchone()[0]
                
                # Get most recent indexing time
                cursor.execute(
                    "SELECT MAX(indexed_at) FROM files WHERE status = ?",
                    (FileStatus.INDEXED.value,)
                )
                last_indexed = cursor.fetchone()[0]
                
                return {
                    "total_files": sum(status_counts.values()),
                    "indexed_files": status_counts.get(FileStatus.INDEXED.value, 0),
                    "failed_files": status_counts.get(FileStatus.FAILED.value, 0),
                    "pending_files": status_counts.get(FileStatus.PENDING.value, 0),
                    "deleted_files": status_counts.get(FileStatus.DELETED.value, 0),
                    "total_sheets": total_sheets,
                    "total_pivot_tables": total_pivots,
                    "total_charts": total_charts,
                    "last_indexed_at": last_indexed
                }
                
        except Exception as e:
            logger.error(f"Error getting indexing statistics: {e}")
            return {}
