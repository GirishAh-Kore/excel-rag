"""File management endpoints for web application"""

import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from pydantic import BaseModel, Field
from src.api.web_auth import get_current_user
from src.api.dependencies import get_indexing_orchestrator, get_metadata_storage
from src.indexing.indexing_orchestrator import IndexingOrchestrator
from src.indexing.metadata_storage import MetadataStorageManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Upload directory configuration
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# File validation
ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".xlsm"}
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ============================================================================
# Request/Response Models
# ============================================================================

class FileUploadResponse(BaseModel):
    """Response for file upload"""
    file_id: str
    filename: str
    size: int
    status: str
    message: str
    indexing_job_id: Optional[str] = None


class FileInfo(BaseModel):
    """File information model"""
    file_id: str
    filename: str
    file_path: str
    size: int
    uploaded_at: datetime
    indexed_at: Optional[datetime] = None
    status: str
    sheets_count: int = 0


class FileListResponse(BaseModel):
    """Response for file list"""
    files: List[FileInfo]
    total: int
    page: int
    page_size: int


class FileDeleteResponse(BaseModel):
    """Response for file deletion"""
    success: bool
    message: str
    file_id: str


class ReindexResponse(BaseModel):
    """Response for file reindexing"""
    success: bool
    message: str
    job_id: str


class IndexingStatusResponse(BaseModel):
    """Response for indexing status"""
    active_jobs: List[dict]
    completed_jobs: List[dict]
    failed_jobs: List[dict]


# ============================================================================
# Helper Functions
# ============================================================================

def validate_file(file: UploadFile) -> tuple[bool, Optional[str]]:
    """Validate uploaded file"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
    
    return True, None


def save_uploaded_file(file: UploadFile) -> tuple[str, Path]:
    """Save uploaded file and return file_id and path"""
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    
    # Create filename with ID to avoid conflicts
    file_ext = Path(file.filename).suffix
    safe_filename = f"{file_id}_{file.filename}"
    file_path = UPLOAD_DIR / safe_filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return file_id, file_path


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
    orchestrator: IndexingOrchestrator = Depends(get_indexing_orchestrator)
):
    """
    Upload Excel file and trigger indexing
    
    - **file**: Excel file (.xlsx, .xls, .xlsm)
    - Maximum file size: 100MB (configurable)
    """
    logger.info(f"File upload request from user {current_user}: {file.filename}")
    
    # Validate file
    is_valid, error_message = validate_file(file)
    if not is_valid:
        logger.warning(f"File validation failed: {error_message}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning
    
    if file_size > MAX_FILE_SIZE_BYTES:
        logger.warning(f"File too large: {file_size} bytes")
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB"
        )
    
    try:
        # Save file
        file_id, file_path = save_uploaded_file(file)
        logger.info(f"File saved: {file_path}")
        
        # Trigger indexing
        try:
            job_id = orchestrator.start_indexing(
                file_paths=[str(file_path)],
                incremental=False
            )
            
            logger.info(f"Indexing started for file {file_id}, job_id: {job_id}")
            
            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                size=file_size,
                status="indexing",
                message="File uploaded and indexing started",
                indexing_job_id=job_id
            )
        except Exception as e:
            logger.error(f"Failed to start indexing: {e}", exc_info=True)
            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                size=file_size,
                status="uploaded",
                message=f"File uploaded but indexing failed: {str(e)}",
                indexing_job_id=None
            )
    
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/list", response_model=FileListResponse)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: str = Depends(get_current_user),
    metadata_storage: MetadataStorageManager = Depends(get_metadata_storage)
):
    """
    List all indexed files with pagination
    
    - **page**: Page number (starting from 1)
    - **page_size**: Number of items per page (max 100)
    """
    logger.info(f"File list request from user {current_user}, page={page}, page_size={page_size}")
    
    try:
        # Get all files from metadata storage
        all_files = metadata_storage.get_all_indexed_files()
        
        # Calculate pagination
        total = len(all_files)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        # Get page of files
        page_files = all_files[start_idx:end_idx]
        
        # Convert to FileInfo models
        file_infos = []
        for file_data in page_files:
            file_infos.append(FileInfo(
                file_id=file_data.get("file_id", file_data.get("md5_checksum", "")),
                filename=file_data.get("name", ""),
                file_path=file_data.get("path", ""),
                size=file_data.get("size", 0),
                uploaded_at=file_data.get("modified_time", datetime.utcnow()),
                indexed_at=file_data.get("indexed_at"),
                status=file_data.get("status", "indexed"),
                sheets_count=file_data.get("sheets_count", 0)
            ))
        
        return FileListResponse(
            files=file_infos,
            total=total,
            page=page,
            page_size=page_size
        )
    
    except Exception as e:
        logger.error(f"Failed to list files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(
    file_id: str,
    current_user: str = Depends(get_current_user),
    metadata_storage: MetadataStorageManager = Depends(get_metadata_storage)
):
    """
    Delete file and remove from index
    
    - **file_id**: Unique file identifier
    """
    logger.info(f"File delete request from user {current_user}: {file_id}")
    
    try:
        # Get file info from metadata
        file_info = metadata_storage.get_file_metadata(file_id)
        
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_id}"
            )
        
        # Delete physical file if it exists
        file_path = Path(file_info.get("path", ""))
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted physical file: {file_path}")
        
        # Remove from metadata storage
        metadata_storage.delete_file_metadata(file_id)
        
        # TODO: Remove from vector store
        # This would require vector store integration
        
        logger.info(f"File deleted successfully: {file_id}")
        
        return FileDeleteResponse(
            success=True,
            message="File deleted successfully",
            file_id=file_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.post("/{file_id}/reindex", response_model=ReindexResponse)
async def reindex_file(
    file_id: str,
    current_user: str = Depends(get_current_user),
    metadata_storage: MetadataStorageManager = Depends(get_metadata_storage),
    orchestrator: IndexingOrchestrator = Depends(get_indexing_orchestrator)
):
    """
    Trigger re-indexing for a specific file
    
    - **file_id**: Unique file identifier
    """
    logger.info(f"File reindex request from user {current_user}: {file_id}")
    
    try:
        # Get file info from metadata
        file_info = metadata_storage.get_file_metadata(file_id)
        
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_id}"
            )
        
        file_path = file_info.get("path", "")
        
        # Check if file exists
        if not Path(file_path).exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found on disk: {file_path}"
            )
        
        # Start indexing
        job_id = orchestrator.start_indexing(
            file_paths=[file_path],
            incremental=False
        )
        
        logger.info(f"Re-indexing started for file {file_id}, job_id: {job_id}")
        
        return ReindexResponse(
            success=True,
            message="Re-indexing started",
            job_id=job_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reindex file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reindex file: {str(e)}"
        )


@router.get("/indexing-status", response_model=IndexingStatusResponse)
async def get_indexing_status(
    current_user: str = Depends(get_current_user),
    orchestrator: IndexingOrchestrator = Depends(get_indexing_orchestrator)
):
    """
    Get status of all indexing jobs
    
    Returns active, completed, and failed indexing jobs.
    """
    logger.info(f"Indexing status request from user {current_user}")
    
    try:
        # Get job statuses from orchestrator
        active_jobs = orchestrator.get_active_jobs()
        completed_jobs = orchestrator.get_completed_jobs()
        failed_jobs = orchestrator.get_failed_jobs()
        
        return IndexingStatusResponse(
            active_jobs=active_jobs,
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs
        )
    
    except Exception as e:
        logger.error(f"Failed to get indexing status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get indexing status: {str(e)}"
        )
