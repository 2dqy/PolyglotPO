"""
Download API endpoints for the Translation Tool.
Handles file downloads and download link management.
"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from typing import Dict, Any
from pathlib import Path

from ..models.api_models import SuccessResponse
from ..core.translation_service import get_translation_service
from ..core.file_manager import get_file_manager
from ..utils.exceptions import JobNotFoundError, StorageError
from ..models.translation_models import TranslationStatus
from loguru import logger

router = APIRouter()


@router.get("/download/{job_id}")
async def download_translated_file(job_id: str):
    """
    Download the translated file for a completed translation job.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        FileResponse with the translated file
    """
    try:
        translation_service = get_translation_service()
        job = translation_service.get_job(job_id)
        
        # Check if job is completed
        if job.status != TranslationStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} is not completed. Current status: {job.status.value}"
            )
        
        # Check if download path exists
        if not job.output_file_path or not Path(job.output_file_path).exists():
            raise HTTPException(
                status_code=404,
                detail="Download file not found. The file may have been cleaned up."
            )
        
        # Get file info
        file_path = Path(job.output_file_path)
        download_filename = file_path.name
        
        logger.info(f"Serving download for job {job_id}: {download_filename}")
        
        # Return file response
        return FileResponse(
            path=str(file_path),
            filename=download_filename,
            media_type="application/x-gettext-translation",
            headers={
                "Content-Disposition": f"attachment; filename={download_filename}",
                "X-Job-ID": job_id,
                "X-Original-Filename": job.filename,
                "X-Target-Language": job.target_language
            }
        )
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to download file for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{job_id}/info", response_model=Dict[str, Any])
async def get_download_info(job_id: str):
    """
    Get download information for a translation job.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        Dict with download information
    """
    try:
        translation_service = get_translation_service()
        file_manager = get_file_manager()
        job = translation_service.get_job(job_id)
        
        # Check if job is completed
        if job.status != TranslationStatus.COMPLETED:
            return {
                "job_id": job_id,
                "available": False,
                "status": job.status.value,
                "message": f"Translation not completed. Current status: {job.status.value}"
            }
        
        # Check if download file exists
        download_available = False
        file_info = None
        
        if job.output_file_path and Path(job.output_file_path).exists():
            try:
                file_info = await file_manager.get_file_info(job.output_file_path)
                download_available = True
            except StorageError:
                download_available = False
        
        result = {
            "job_id": job_id,
            "available": download_available,
            "status": job.status.value,
            "filename": job.download_filename,
            "original_filename": job.filename,
            "target_language": job.target_language,
            "translated_entries": job.progress.successful_translations if job.progress else 0,
            "total_entries": job.progress.total_entries if job.progress else 0
        }
        
        if file_info:
            result.update({
                "file_size": file_info["file_size"],
                "created_at": file_info["created_at"].isoformat(),
                "download_url": f"/api/v1/download/{job_id}"
            })
        
        return result
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get download info for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/download/{job_id}/prepare", response_model=SuccessResponse)
async def prepare_download(job_id: str):
    """
    Prepare download file for a completed translation job.
    This can be used to regenerate download files if they were cleaned up.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        SuccessResponse confirmation
    """
    try:
        translation_service = get_translation_service()
        file_manager = get_file_manager()
        job = translation_service.get_job(job_id)
        
        # Check if job is completed
        if job.status != TranslationStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot prepare download for job {job_id}. Status: {job.status.value}"
            )
        
        # Check if processed file exists
        job_files = await file_manager.get_job_files(job_id)
        processed_file = job_files.get("processed")
        
        if not processed_file or not Path(processed_file).exists():
            raise HTTPException(
                status_code=404,
                detail="Processed file not found. The job may have been cleaned up."
            )
        
        # Get processed file info
        processed_file_info = await file_manager.get_file_info(processed_file)
        processed_file_info.update({
            "processed_filename": Path(processed_file).name,
            "target_language": job.target_language
        })
        
        # Prepare download file
        download_info = await file_manager.prepare_download_file(
            job_id=job_id,
            processed_file_info=processed_file_info
        )
        
        # Update job with new download info
        job.output_file_path = download_info["download_path"]
        
        logger.info(f"Download prepared for job {job_id}")
        
        return SuccessResponse(
            message=f"Download file prepared for job {job_id}"
        )
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to prepare download for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/download/{job_id}", response_model=SuccessResponse)
async def delete_download_file(job_id: str):
    """
    Delete the download file for a translation job.
    The job record will remain but the download file will be removed.
    
    Args:
        job_id: Translation job ID
        
    Returns:
        SuccessResponse confirmation
    """
    try:
        translation_service = get_translation_service()
        job = translation_service.get_job(job_id)
        
        # Check if download file exists
        if job.output_file_path and Path(job.output_file_path).exists():
            # Remove download file
            Path(job.output_file_path).unlink()
            
            # Clear download info from job
            job.output_file_path = None
            
            logger.info(f"Download file deleted for job {job_id}")
            
            return SuccessResponse(
                message=f"Download file deleted for job {job_id}"
            )
        else:
            return SuccessResponse(
                message=f"No download file found for job {job_id}"
            )
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete download file for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{job_id}/preview")
async def preview_translated_file(job_id: str, lines: int = 50):
    """
    Preview the first few lines of a translated file.
    
    Args:
        job_id: Translation job ID
        lines: Number of lines to preview (default: 50, max: 200)
        
    Returns:
        Dict with file preview
    """
    try:
        # Limit preview lines
        lines = min(lines, 200)
        
        translation_service = get_translation_service()
        file_manager = get_file_manager()
        job = translation_service.get_job(job_id)
        
        # Check if job is completed
        if job.status != TranslationStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Job {job_id} is not completed. Current status: {job.status.value}"
            )
        
        # Check if download file exists
        if not job.output_file_path or not Path(job.output_file_path).exists():
            raise HTTPException(
                status_code=404,
                detail="Download file not found"
            )
        
        # Read file content
        content = await file_manager.get_file_content(job.output_file_path)
        
        # Split into lines and take the requested number
        content_lines = content.split('\n')
        preview_lines = content_lines[:lines]
        
        return {
            "job_id": job_id,
            "filename": job.download_filename,
            "total_lines": len(content_lines),
            "preview_lines": len(preview_lines),
            "content": '\n'.join(preview_lines),
            "truncated": len(content_lines) > lines
        }
        
    except JobNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to preview file for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 