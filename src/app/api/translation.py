"""
Translation API endpoints for the Translation Tool.
Handles translation job creation, status monitoring, and management.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional

from ..models.translation_models import (
    TranslationJobCreate, 
    TranslationJobResponse, 
    TranslationProgress,
    TranslationStatus
)
from ..models.api_models import SuccessResponse, ErrorResponse
from ..core.translation_service import get_translation_service
from ..core.file_manager import get_file_manager
from ..utils.exceptions import (
    JobNotFoundError,
    JobProcessingError,
    TranslationServiceError,
    ERROR_HTTP_MAPPINGS
)
from loguru import logger

router = APIRouter()


@router.post("/translate", response_model=TranslationJobResponse)
async def create_translation_job(
    job_request: TranslationJobCreate,
    background_tasks: BackgroundTasks
):
    """
    Create a new translation job.
    
    Args:
        job_request: Translation job creation request
        background_tasks: FastAPI background tasks
        
    Returns:
        TranslationJobResponse with job details
    """
    try:
        translation_service = get_translation_service()
        file_manager = get_file_manager()
        
        # Get file info from upload
        files = await file_manager.get_job_files(job_request.file_id)
        if not files.get("upload"):
            raise HTTPException(status_code=404, detail="Uploaded file not found")
        
        # Create file info dict
        file_info = {
            "job_id": job_request.file_id,
            "original_filename": job_request.filename,
            "file_path": files["upload"],
            "file_size": 0  # Will be updated by file manager
        }
        
        # Create translation job
        job = await translation_service.create_translation_job(
            file_info=file_info,
            target_language=job_request.target_language,
            source_language=job_request.source_language
        )
        
        # Start translation in background
        background_tasks.add_task(translation_service.start_translation, job.job_id)
        
        logger.info(f"Translation job created: {job.job_id}")
        
        return TranslationJobResponse.from_translation_job(job)
        
    except Exception as e:
        logger.error(f"Failed to create translation job: {e}")
        status_code = ERROR_HTTP_MAPPINGS.get(type(e), 500)
        raise HTTPException(status_code=status_code, detail=str(e))


@router.get("/translate/{job_id}", response_model=TranslationJobResponse)
async def get_translation_job(job_id: str):
    """
    Get translation job details.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        TranslationJobResponse with job details
    """
    try:
        translation_service = get_translation_service()
        job = translation_service.get_job(job_id)
        
        return TranslationJobResponse.from_translation_job(job)
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get translation job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/translate/{job_id}/progress", response_model=TranslationProgress)
async def get_translation_progress(job_id: str):
    """
    Get translation job progress.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        TranslationProgress with current progress
    """
    try:
        translation_service = get_translation_service()
        job = translation_service.get_job(job_id)
        
        # Get progress from job's progress object or create a new one
        if job.progress:
            return job.progress
        else:
            return TranslationProgress(
                job_id=job.job_id,
                status=job.status,
                total_entries=0,
                processed_entries=0,
                successful_translations=0,
                failed_translations=0,
                started_at=job.started_at,
                completed_at=job.completed_at,
                current_error=job.error_message,
                estimated_completion=None
            )
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get progress for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translate/{job_id}/cancel", response_model=SuccessResponse)
async def cancel_translation_job(job_id: str):
    """
    Cancel a translation job.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        SuccessResponse confirmation
    """
    try:
        translation_service = get_translation_service()
        await translation_service.cancel_job(job_id)
        
        logger.info(f"Translation job cancelled: {job_id}")
        
        return SuccessResponse(message=f"Translation job {job_id} cancelled successfully")
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except JobProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel translation job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/translate/{job_id}/retry", response_model=TranslationJobResponse)
async def retry_translation_job(job_id: str):
    """
    Retry a failed translation job.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        TranslationJobResponse with updated job details
    """
    try:
        translation_service = get_translation_service()
        await translation_service.retry_job(job_id)
        
        job = translation_service.get_job(job_id)
        
        logger.info(f"Translation job retried: {job_id}")
        
        return TranslationJobResponse.from_translation_job(job)
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except JobProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to retry translation job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/translate", response_model=List[TranslationJobResponse])
async def list_translation_jobs(
    status: Optional[TranslationStatus] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    List translation jobs with optional filtering.
    
    Args:
        status: Optional status filter
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip
        
    Returns:
        List of TranslationJobResponse
    """
    try:
        translation_service = get_translation_service()
        
        if status:
            jobs = translation_service.get_jobs_by_status(status)
        else:
            jobs = translation_service.get_all_jobs()
        
        # Sort by creation time (newest first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        paginated_jobs = jobs[offset:offset + limit]
        
        return [TranslationJobResponse.from_translation_job(job) for job in paginated_jobs]
        
    except Exception as e:
        logger.error(f"Failed to list translation jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/translate/{job_id}", response_model=SuccessResponse)
async def delete_translation_job(job_id: str):
    """
    Delete a translation job and clean up files.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        SuccessResponse confirmation
    """
    try:
        translation_service = get_translation_service()
        file_manager = get_file_manager()
        
        # Check if job exists
        job = translation_service.get_job(job_id)
        
        # Can only delete completed or failed jobs
        if job.status in [TranslationStatus.PENDING, TranslationStatus.PROCESSING]:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete job in progress. Cancel the job first."
            )
        
        # Clean up files
        await file_manager.cleanup_job_files(job_id)
        
        # Remove job from service
        del translation_service.jobs[job_id]
        
        # Clean up progress callbacks
        if job_id in translation_service._progress_callbacks:
            del translation_service._progress_callbacks[job_id]
        
        logger.info(f"Translation job deleted: {job_id}")
        
        return SuccessResponse(message=f"Translation job {job_id} deleted successfully")
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete translation job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 