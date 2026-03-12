"""Indexing API endpoints"""

import logging
import asyncio
import uuid
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from src.api.models import (
    IndexRequest,
    IndexResponse,
    IndexStatusResponse,
    IndexReportResponse,
    IndexControlResponse,
    ErrorResponse
)
from src.api.dependencies import (
    get_indexing_orchestrator,
    require_authentication,
    get_correlation_id
)
from src.indexing.indexing_orchestrator import IndexingOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory job storage (in production, use Redis or database)
indexing_jobs: Dict[str, Dict[str, Any]] = {}


@router.post(
    "/full",
    response_model=IndexResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Trigger full indexing",
    description="Initiates full indexing of all Excel files in Google Drive"
)
async def full_index(
    request: IndexRequest,
    orchestrator: IndexingOrchestrator = Depends(get_indexing_orchestrator),
    auth_service = Depends(require_authentication),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Trigger full indexing.
    
    Indexes all Excel files in Google Drive, optionally filtered by folder or file patterns.
    Returns a job ID for tracking progress.
    """
    try:
        logger.info(
            f"Starting full indexing",
            extra={
                'correlation_id': correlation_id,
                'folder_id': request.folder_id,
                'file_filters': request.file_filters
            }
        )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Store job info
        indexing_jobs[job_id] = {
            'job_id': job_id,
            'type': 'full',
            'status': 'running',
            'started_at': datetime.utcnow(),
            'folder_id': request.folder_id,
            'file_filters': request.file_filters,
            'force_reindex': request.force_reindex
        }
        
        # Start indexing in background
        asyncio.create_task(
            run_full_indexing(
                job_id,
                orchestrator,
                request.folder_id,
                request.file_filters,
                request.force_reindex
            )
        )
        
        logger.info(
            f"Full indexing job created",
            extra={'correlation_id': correlation_id, 'job_id': job_id}
        )
        
        return IndexResponse(
            job_id=job_id,
            status='running',
            message='Full indexing started successfully'
        )
        
    except Exception as e:
        logger.error(
            f"Failed to start full indexing: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start indexing: {str(e)}"
        )


@router.post(
    "/incremental",
    response_model=IndexResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Authentication required"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Trigger incremental indexing",
    description="Indexes only changed files since last indexing"
)
async def incremental_index(
    request: IndexRequest,
    orchestrator: IndexingOrchestrator = Depends(get_indexing_orchestrator),
    auth_service = Depends(require_authentication),
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Trigger incremental indexing.
    
    Indexes only files that have been added, modified, or deleted since last indexing.
    Returns a job ID for tracking progress.
    """
    try:
        logger.info(
            f"Starting incremental indexing",
            extra={
                'correlation_id': correlation_id,
                'folder_id': request.folder_id,
                'file_filters': request.file_filters
            }
        )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Store job info
        indexing_jobs[job_id] = {
            'job_id': job_id,
            'type': 'incremental',
            'status': 'running',
            'started_at': datetime.utcnow(),
            'folder_id': request.folder_id,
            'file_filters': request.file_filters
        }
        
        # Start indexing in background
        asyncio.create_task(
            run_incremental_indexing(
                job_id,
                orchestrator,
                request.folder_id,
                request.file_filters
            )
        )
        
        logger.info(
            f"Incremental indexing job created",
            extra={'correlation_id': correlation_id, 'job_id': job_id}
        )
        
        return IndexResponse(
            job_id=job_id,
            status='running',
            message='Incremental indexing started successfully'
        )
        
    except Exception as e:
        logger.error(
            f"Failed to start incremental indexing: {e}",
            extra={'correlation_id': correlation_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start indexing: {str(e)}"
        )


@router.get(
    "/status/{job_id}",
    response_model=IndexStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get indexing status",
    description="Returns current status and progress of an indexing job"
)
async def get_status(
    job_id: str,
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Get indexing job status.
    
    Returns current status, progress percentage, and other job details.
    """
    try:
        # Check if job exists
        if job_id not in indexing_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = indexing_jobs[job_id]
        
        # Calculate estimated completion
        estimated_completion = None
        if job.get('progress_percentage', 0) > 0:
            elapsed = (datetime.utcnow() - job['started_at']).total_seconds()
            total_estimated = elapsed / (job['progress_percentage'] / 100)
            remaining = total_estimated - elapsed
            estimated_completion = datetime.utcnow().timestamp() + remaining
            estimated_completion = datetime.fromtimestamp(estimated_completion)
        
        return IndexStatusResponse(
            job_id=job_id,
            status=job.get('status', 'unknown'),
            progress_percentage=job.get('progress_percentage', 0.0),
            current_file=job.get('current_file'),
            files_processed=job.get('files_processed', 0),
            files_total=job.get('files_total', 0),
            started_at=job['started_at'],
            estimated_completion=estimated_completion
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting job status: {e}",
            extra={'correlation_id': correlation_id, 'job_id': job_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}"
        )


@router.get(
    "/report/{job_id}",
    response_model=IndexReportResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Get indexing report",
    description="Returns detailed report of completed indexing job"
)
async def get_report(
    job_id: str,
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Get indexing job report.
    
    Returns detailed statistics and results of a completed indexing job.
    """
    try:
        # Check if job exists
        if job_id not in indexing_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = indexing_jobs[job_id]
        
        # Calculate duration
        completed_at = job.get('completed_at', datetime.utcnow())
        duration = (completed_at - job['started_at']).total_seconds()
        
        return IndexReportResponse(
            job_id=job_id,
            status=job.get('status', 'unknown'),
            files_processed=job.get('files_processed', 0),
            files_failed=job.get('files_failed', 0),
            files_skipped=job.get('files_skipped', 0),
            sheets_indexed=job.get('sheets_indexed', 0),
            embeddings_generated=job.get('embeddings_generated', 0),
            duration_seconds=duration,
            started_at=job['started_at'],
            completed_at=job.get('completed_at'),
            errors=job.get('errors', [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting job report: {e}",
            extra={'correlation_id': correlation_id, 'job_id': job_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job report: {str(e)}"
        )


@router.post(
    "/pause/{job_id}",
    response_model=IndexControlResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Invalid operation"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Pause indexing job",
    description="Pauses a running indexing job"
)
async def pause_job(
    job_id: str,
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Pause indexing job.
    
    Pauses a running indexing job. Can be resumed later.
    """
    try:
        if job_id not in indexing_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = indexing_jobs[job_id]
        
        if job['status'] != 'running':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is not running (current status: {job['status']})"
            )
        
        # Update status
        job['status'] = 'paused'
        job['paused_at'] = datetime.utcnow()
        
        logger.info(
            f"Job paused",
            extra={'correlation_id': correlation_id, 'job_id': job_id}
        )
        
        return IndexControlResponse(
            job_id=job_id,
            action='pause',
            success=True,
            message='Job paused successfully'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error pausing job: {e}",
            extra={'correlation_id': correlation_id, 'job_id': job_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause job: {str(e)}"
        )


@router.post(
    "/resume/{job_id}",
    response_model=IndexControlResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Invalid operation"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Resume indexing job",
    description="Resumes a paused indexing job"
)
async def resume_job(
    job_id: str,
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Resume indexing job.
    
    Resumes a paused indexing job.
    """
    try:
        if job_id not in indexing_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = indexing_jobs[job_id]
        
        if job['status'] != 'paused':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Job is not paused (current status: {job['status']})"
            )
        
        # Update status
        job['status'] = 'running'
        job['resumed_at'] = datetime.utcnow()
        
        logger.info(
            f"Job resumed",
            extra={'correlation_id': correlation_id, 'job_id': job_id}
        )
        
        return IndexControlResponse(
            job_id=job_id,
            action='resume',
            success=True,
            message='Job resumed successfully'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error resuming job: {e}",
            extra={'correlation_id': correlation_id, 'job_id': job_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume job: {str(e)}"
        )


@router.post(
    "/stop/{job_id}",
    response_model=IndexControlResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Job not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    },
    summary="Stop indexing job",
    description="Stops a running or paused indexing job"
)
async def stop_job(
    job_id: str,
    correlation_id: str = Depends(get_correlation_id)
):
    """
    Stop indexing job.
    
    Stops a running or paused indexing job. Cannot be resumed.
    """
    try:
        if job_id not in indexing_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        job = indexing_jobs[job_id]
        
        # Update status
        job['status'] = 'stopped'
        job['stopped_at'] = datetime.utcnow()
        job['completed_at'] = datetime.utcnow()
        
        logger.info(
            f"Job stopped",
            extra={'correlation_id': correlation_id, 'job_id': job_id}
        )
        
        return IndexControlResponse(
            job_id=job_id,
            action='stop',
            success=True,
            message='Job stopped successfully'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error stopping job: {e}",
            extra={'correlation_id': correlation_id, 'job_id': job_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop job: {str(e)}"
        )


@router.websocket("/ws/{job_id}")
async def websocket_progress(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint for real-time progress updates.
    
    Streams progress updates for an indexing job.
    """
    await websocket.accept()
    
    try:
        logger.info(f"WebSocket connection established for job {job_id}")
        
        # Check if job exists
        if job_id not in indexing_jobs:
            await websocket.send_json({
                'error': 'Job not found',
                'job_id': job_id
            })
            await websocket.close()
            return
        
        # Stream updates
        while True:
            job = indexing_jobs.get(job_id)
            
            if not job:
                await websocket.send_json({'error': 'Job not found'})
                break
            
            # Send current status
            await websocket.send_json({
                'job_id': job_id,
                'status': job.get('status'),
                'progress_percentage': job.get('progress_percentage', 0),
                'current_file': job.get('current_file'),
                'files_processed': job.get('files_processed', 0),
                'files_total': job.get('files_total', 0)
            })
            
            # Break if job is completed
            if job.get('status') in ['completed', 'failed', 'stopped']:
                break
            
            # Wait before next update
            await asyncio.sleep(1)
        
        await websocket.close()
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    except Exception as e:
        logger.error(f"WebSocket error for job {job_id}: {e}", exc_info=True)
        try:
            await websocket.send_json({'error': str(e)})
            await websocket.close()
        except:
            pass


# ============================================================================
# Background Tasks
# ============================================================================

async def run_full_indexing(
    job_id: str,
    orchestrator: IndexingOrchestrator,
    folder_id: str = None,
    file_filters: list = None,
    force_reindex: bool = False
):
    """Run full indexing in background"""
    try:
        # Update job with progress callback
        def progress_callback(current, total, current_file):
            if job_id in indexing_jobs:
                indexing_jobs[job_id].update({
                    'files_processed': current,
                    'files_total': total,
                    'current_file': current_file,
                    'progress_percentage': (current / total * 100) if total > 0 else 0
                })
        
        # Run indexing
        report = await asyncio.to_thread(
            orchestrator.index_all_files,
            folder_id=folder_id,
            file_filters=file_filters,
            force_reindex=force_reindex,
            progress_callback=progress_callback
        )
        
        # Update job with results
        indexing_jobs[job_id].update({
            'status': 'completed',
            'completed_at': datetime.utcnow(),
            'files_processed': report.files_processed,
            'files_failed': report.files_failed,
            'files_skipped': report.files_skipped,
            'sheets_indexed': report.sheets_indexed,
            'embeddings_generated': report.embeddings_generated,
            'errors': report.errors
        })
        
    except Exception as e:
        logger.error(f"Full indexing failed for job {job_id}: {e}", exc_info=True)
        indexing_jobs[job_id].update({
            'status': 'failed',
            'completed_at': datetime.utcnow(),
            'errors': [str(e)]
        })


async def run_incremental_indexing(
    job_id: str,
    orchestrator: IndexingOrchestrator,
    folder_id: str = None,
    file_filters: list = None
):
    """Run incremental indexing in background"""
    try:
        # Update job with progress callback
        def progress_callback(current, total, current_file):
            if job_id in indexing_jobs:
                indexing_jobs[job_id].update({
                    'files_processed': current,
                    'files_total': total,
                    'current_file': current_file,
                    'progress_percentage': (current / total * 100) if total > 0 else 0
                })
        
        # Run indexing
        report = await asyncio.to_thread(
            orchestrator.index_changed_files,
            folder_id=folder_id,
            file_filters=file_filters,
            progress_callback=progress_callback
        )
        
        # Update job with results
        indexing_jobs[job_id].update({
            'status': 'completed',
            'completed_at': datetime.utcnow(),
            'files_processed': report.files_processed,
            'files_failed': report.files_failed,
            'files_skipped': report.files_skipped,
            'sheets_indexed': report.sheets_indexed,
            'embeddings_generated': report.embeddings_generated,
            'errors': report.errors
        })
        
    except Exception as e:
        logger.error(f"Incremental indexing failed for job {job_id}: {e}", exc_info=True)
        indexing_jobs[job_id].update({
            'status': 'failed',
            'completed_at': datetime.utcnow(),
            'errors': [str(e)]
        })
