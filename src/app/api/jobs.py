"""
Jobs API endpoints for the Translation Tool.
Handles job listing, filtering, and bulk operations.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ..models.translation_models import TranslationJobResponse, TranslationStatus
from ..models.api_models import SuccessResponse
from ..core.translation_service import get_translation_service
from ..utils.exceptions import JobNotFoundError
from loguru import logger

router = APIRouter()


@router.get("/jobs", response_model=List[TranslationJobResponse])
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by job status (comma-separated for multiple)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    sort_by: str = Query("created_at", description="Sort field (created_at, filename, status)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)")
):
    """
    List translation jobs with filtering and pagination.
    
    Args:
        status: Optional status filter
        limit: Maximum number of jobs to return (1-100)
        offset: Number of jobs to skip for pagination
        sort_by: Field to sort by
        sort_order: Sort order (ascending or descending)
        
    Returns:
        List of TranslationJobResponse
    """
    try:
        translation_service = get_translation_service()
        
        # Get jobs based on status filter
        if status:
            # Parse comma-separated status values
            status_list = [s.strip() for s in status.split(',')]
            status_enums = []
            
            for status_str in status_list:
                try:
                    status_enums.append(TranslationStatus(status_str))
                except ValueError:
                    logger.warning(f"Invalid status filter: {status_str}")
                    continue
            
            if status_enums:
                # Get jobs matching any of the specified statuses
                jobs = []
                for status_enum in status_enums:
                    jobs.extend(translation_service.get_jobs_by_status(status_enum))
                
                # Remove duplicates while preserving order
                seen = set()
                unique_jobs = []
                for job in jobs:
                    if job.job_id not in seen:
                        seen.add(job.job_id)
                        unique_jobs.append(job)
                jobs = unique_jobs
            else:
                jobs = translation_service.get_all_jobs()
        else:
            jobs = translation_service.get_all_jobs()
        
        # Sort jobs
        reverse_order = sort_order.lower() == "desc"
        
        if sort_by == "created_at":
            jobs.sort(key=lambda x: x.created_at, reverse=reverse_order)
        elif sort_by == "filename":
            jobs.sort(key=lambda x: x.filename.lower(), reverse=reverse_order)
        elif sort_by == "status":
            jobs.sort(key=lambda x: x.status.value, reverse=reverse_order)
        else:
            # Default to created_at
            jobs.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        total_jobs = len(jobs)
        paginated_jobs = jobs[offset:offset + limit]
        
        logger.info(f"Listed {len(paginated_jobs)} jobs (total: {total_jobs})")
        
        return [TranslationJobResponse.from_translation_job(job) for job in paginated_jobs]
        
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/stats", response_model=Dict[str, Any])
async def get_job_stats():
    """
    Get job statistics and summary.
    
    Returns:
        Dict with job statistics
    """
    try:
        translation_service = get_translation_service()
        jobs = translation_service.get_all_jobs()
        
        # Count by status
        status_counts = {}
        for status in TranslationStatus:
            status_counts[status.value] = len([j for j in jobs if j.status == status])
        
        # Calculate processing times for completed jobs
        completed_jobs = [j for j in jobs if j.status == TranslationStatus.COMPLETED and j.started_at and j.completed_at]
        
        avg_processing_time = None
        if completed_jobs:
            total_time = sum((j.completed_at - j.started_at).total_seconds() for j in completed_jobs)
            avg_processing_time = total_time / len(completed_jobs)
        
        # Recent activity (last 24 hours)
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_jobs = [j for j in jobs if j.created_at > recent_cutoff]
        
        stats = {
            "total_jobs": len(jobs),
            "status_counts": status_counts,
            "recent_jobs_24h": len(recent_jobs),
            "average_processing_time_seconds": avg_processing_time,
            "active_jobs": len([j for j in jobs if j.status in [TranslationStatus.PENDING, TranslationStatus.PROCESSING]])
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get job stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=TranslationJobResponse)
async def get_job(job_id: str):
    """
    Get detailed information about a specific job.
    
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
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}", response_model=SuccessResponse)
async def delete_job(job_id: str):
    """
    Delete a translation job and its associated files.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        SuccessResponse confirmation
    """
    try:
        translation_service = get_translation_service()
        job = translation_service.get_job(job_id)
        
        # Can only delete completed or failed jobs
        if job.status in [TranslationStatus.PENDING, TranslationStatus.PROCESSING]:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete job in progress. Cancel the job first."
            )
        
        # Delete the job (handled by translation API)
        from .translation import delete_translation_job
        return await delete_translation_job(job_id)
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/cleanup", response_model=SuccessResponse)
async def cleanup_old_jobs(
    older_than_hours: int = Query(24, ge=1, le=168, description="Clean up jobs older than this many hours")
):
    """
    Clean up old completed jobs and their files.
    
    Args:
        older_than_hours: Remove jobs older than this many hours (1-168)
        
    Returns:
        SuccessResponse with cleanup summary
    """
    try:
        translation_service = get_translation_service()
        
        # Get count before cleanup
        jobs_before = len(translation_service.get_all_jobs())
        
        # Run cleanup
        await translation_service.cleanup_completed_jobs(older_than_hours)
        
        # Get count after cleanup
        jobs_after = len(translation_service.get_all_jobs())
        cleaned_count = jobs_before - jobs_after
        
        logger.info(f"Cleaned up {cleaned_count} old jobs")
        
        return SuccessResponse(
            message=f"Cleaned up {cleaned_count} jobs older than {older_than_hours} hours"
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup old jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/cleanup-all", response_model=SuccessResponse)
async def cleanup_all_completed_jobs():
    """
    Clean up ALL completed and failed jobs immediately.
    
    Returns:
        SuccessResponse with cleanup summary
    """
    try:
        translation_service = get_translation_service()
        
        # Get completed and failed jobs
        completed_jobs = translation_service.get_jobs_by_status(TranslationStatus.COMPLETED)
        failed_jobs = translation_service.get_jobs_by_status(TranslationStatus.FAILED)
        cancelled_jobs = translation_service.get_jobs_by_status(TranslationStatus.CANCELLED)
        
        all_cleanup_jobs = completed_jobs + failed_jobs + cancelled_jobs
        cleaned_count = 0
        
        # Delete each job
        for job in all_cleanup_jobs:
            try:
                from .translation import delete_translation_job
                await delete_translation_job(job.job_id)
                cleaned_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete job {job.job_id}: {e}")
        
        logger.info(f"Cleaned up {cleaned_count} completed/failed jobs")
        
        return SuccessResponse(
            message=f"Cleaned up {cleaned_count} completed/failed jobs"
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup all completed jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/cleanup-files", response_model=SuccessResponse)
async def cleanup_orphaned_files():
    """
    Clean up orphaned files that don't have corresponding jobs.
    
    Returns:
        SuccessResponse with cleanup summary
    """
    try:
        from ..core.file_manager import get_file_manager
        
        file_manager = get_file_manager()
        translation_service = get_translation_service()
        
        # Get all job IDs
        all_jobs = translation_service.get_all_jobs()
        active_job_ids = {job.job_id for job in all_jobs}
        
        # Check storage directories for orphaned files
        cleaned_dirs = 0
        cleaned_files = 0
        
        for base_dir in [file_manager.upload_dir, file_manager.processed_dir, file_manager.download_dir]:
            if not base_dir.exists():
                continue
                
            # Check for subdirectories (new pattern)
            for job_dir in base_dir.iterdir():
                if job_dir.is_dir():
                    job_id = job_dir.name
                    if job_id not in active_job_ids:
                        # This is an orphaned directory
                        await file_manager.cleanup_job_files(job_id)
                        cleaned_dirs += 1
                        
            # Check for direct files (old pattern: {job_id}_{filename})
            for file_path in base_dir.iterdir():
                if file_path.is_file():
                    filename = file_path.name
                    # Extract job_id from filename pattern
                    if '_' in filename:
                        potential_job_id = filename.split('_')[0]
                        # Check if it looks like a UUID
                        if len(potential_job_id) == 36 and potential_job_id.count('-') == 4:
                            if potential_job_id not in active_job_ids:
                                # This is an orphaned file
                                try:
                                    file_path.unlink()
                                    cleaned_files += 1
                                    logger.info(f"Cleaned up orphaned file: {file_path}")
                                except Exception as e:
                                    logger.warning(f"Failed to delete orphaned file {file_path}: {e}")
        
        total_cleaned = cleaned_dirs + cleaned_files
        logger.info(f"Cleaned up {cleaned_dirs} orphaned directories and {cleaned_files} orphaned files")
        
        return SuccessResponse(
            message=f"Cleaned up {total_cleaned} orphaned items ({cleaned_dirs} directories, {cleaned_files} files)"
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/cancel-all", response_model=SuccessResponse)
async def cancel_all_pending_jobs():
    """
    Cancel all pending translation jobs.
    
    Returns:
        SuccessResponse with cancellation summary
    """
    try:
        translation_service = get_translation_service()
        
        # Get pending jobs
        pending_jobs = translation_service.get_jobs_by_status(TranslationStatus.PENDING)
        processing_jobs = translation_service.get_jobs_by_status(TranslationStatus.PROCESSING)
        
        cancelled_count = 0
        
        # Cancel pending jobs
        for job in pending_jobs:
            try:
                await translation_service.cancel_job(job.job_id)
                cancelled_count += 1
            except Exception as e:
                logger.warning(f"Failed to cancel job {job.job_id}: {e}")
        
        # Cancel processing jobs
        for job in processing_jobs:
            try:
                await translation_service.cancel_job(job.job_id)
                cancelled_count += 1
            except Exception as e:
                logger.warning(f"Failed to cancel job {job.job_id}: {e}")
        
        logger.info(f"Cancelled {cancelled_count} jobs")
        
        return SuccessResponse(
            message=f"Cancelled {cancelled_count} active jobs"
        )
        
    except Exception as e:
        logger.error(f"Failed to cancel all jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/search/{query}", response_model=List[TranslationJobResponse])
async def search_jobs(
    query: str,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results")
):
    """
    Search translation jobs by filename or job ID.
    
    Args:
        query: Search query (filename or job ID)
        limit: Maximum number of results to return
        
    Returns:
        List of matching TranslationJobResponse
    """
    try:
        translation_service = get_translation_service()
        jobs = translation_service.get_all_jobs()
        
        # Search by job ID or filename
        query_lower = query.lower()
        matching_jobs = []
        
        for job in jobs:
            if (query_lower in job.job_id.lower() or 
                query_lower in job.filename.lower()):
                matching_jobs.append(job)
        
        # Sort by relevance (exact matches first, then creation time)
        def relevance_score(job):
            score = 0
            if query_lower == job.job_id.lower():
                score += 100
            elif query_lower == job.filename.lower():
                score += 50
            elif job.job_id.lower().startswith(query_lower):
                score += 25
            elif job.filename.lower().startswith(query_lower):
                score += 10
            return score
        
        matching_jobs.sort(key=lambda x: (relevance_score(x), x.created_at), reverse=True)
        
        # Apply limit
        results = matching_jobs[:limit]
        
        logger.info(f"Found {len(results)} jobs matching '{query}'")
        
        return [TranslationJobResponse.from_translation_job(job) for job in results]
        
    except Exception as e:
        logger.error(f"Failed to search jobs with query '{query}': {e}")
        raise HTTPException(status_code=500, detail=str(e)) 