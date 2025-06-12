"""
File upload API endpoints for PO files.
Handles file upload, validation, and initial processing.
"""

import uuid
import shutil
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger

from ..config import settings
from ..core.po_parser import POFileParser
from ..models.api_models import FileUploadResponse, ErrorResponse, SuccessResponse
from ..models.po_models import POFile


router = APIRouter()

# Initialize parser
po_parser = POFileParser()


async def get_po_parser() -> POFileParser:
    """Dependency to get PO parser instance."""
    return po_parser


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PO file to upload"),
    parser: POFileParser = Depends(get_po_parser)
):
    """
    Upload and validate a PO file.
    
    Args:
        file: Uploaded PO file
        parser: PO file parser dependency
        
    Returns:
        FileUploadResponse: Upload result with file information
        
    Raises:
        HTTPException: If upload fails or file is invalid
    """
    try:
        logger.info(f"Received file upload: {file.filename}")
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Check file extension
        file_path = Path(file.filename)
        if file_path.suffix not in settings.file_config.allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file extension. Allowed: {settings.file_config.allowed_extensions}"
            )
        
        # Check file size
        if hasattr(file, 'size') and file.size and file.size > settings.file_config.max_file_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {settings.file_config.max_file_size} bytes"
            )
        
        # Generate unique file ID and save path
        file_id = str(uuid.uuid4())
        upload_filename = f"{file_id}_{file.filename}"
        upload_path = settings.upload_dir / upload_filename
        
        # Save uploaded file
        try:
            with open(upload_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            logger.error(f"Error saving uploaded file: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file")
        
        # Get actual file size
        file_size = upload_path.stat().st_size
        
        # Validate PO file structure
        is_valid, validation_errors = await parser.validate_file(str(upload_path))
        
        if not is_valid:
            # Clean up invalid file
            background_tasks.add_task(cleanup_file, upload_path)
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid PO file: {'; '.join(validation_errors)}"
            )
        
        # Parse PO file to get statistics
        po_file_stats = {"total_entries": 0, "translated_entries": 0, "untranslated_entries": 0}
        
        try:
            po_file = await parser.parse_file(str(upload_path))
            po_file_stats = {
                "total_entries": po_file.total_entries,
                "translated_entries": po_file.translated_entries,
                "untranslated_entries": po_file.untranslated_entries
            }
        except Exception as e:
            logger.warning(f"Could not parse PO file for statistics: {e}")
            # File is valid but couldn't extract stats - continue anyway
        
        # Schedule cleanup of old files
        background_tasks.add_task(cleanup_old_files)
        
        logger.info(f"Successfully uploaded file: {file.filename} (ID: {file_id})")
        
        return FileUploadResponse(
            filename=file.filename,
            file_id=file_id,
            file_size=file_size,
            upload_path=str(upload_path),
            is_valid=is_valid,
            validation_errors=validation_errors,
            **po_file_stats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during file upload: {e}")
        raise HTTPException(status_code=500, detail="File upload failed")
    finally:
        # Close the file
        if file.file and not file.file.closed:
            file.file.close()


@router.post("/upload/validate", response_model=SuccessResponse)
async def validate_file_only(
    file: UploadFile = File(..., description="PO file to validate"),
    parser: POFileParser = Depends(get_po_parser)
):
    """
    Validate a PO file without saving it.
    
    Args:
        file: PO file to validate
        parser: PO file parser dependency
        
    Returns:
        SuccessResponse: Validation result
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Create temporary file for validation
        temp_path = settings.upload_dir / f"temp_{uuid.uuid4()}_{file.filename}"
        
        try:
            # Save temporary file
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Validate
            is_valid, validation_errors = await parser.validate_file(str(temp_path))
            
            if not is_valid:
                return JSONResponse(
                    status_code=400,
                    content=ErrorResponse(
                        error="File validation failed",
                        details={"validation_errors": validation_errors}
                    ).dict()
                )
            
            # Get basic statistics
            stats = {}
            try:
                po_file = await parser.parse_file(str(temp_path))
                stats = po_file.get_statistics()
            except Exception as e:
                logger.warning(f"Could not extract statistics: {e}")
            
            return SuccessResponse(
                message="File is valid",
                data={
                    "filename": file.filename,
                    "is_valid": True,
                    "statistics": stats
                }
            )
            
        finally:
            # Clean up temporary file
            if temp_path.exists():
                temp_path.unlink()
                
    except Exception as e:
        logger.error(f"Error validating file: {e}")
        raise HTTPException(status_code=500, detail="File validation failed")
    finally:
        if file.file and not file.file.closed:
            file.file.close()


@router.get("/upload/{file_id}/info")
async def get_file_info(
    file_id: str,
    parser: POFileParser = Depends(get_po_parser)
):
    """
    Get information about an uploaded file.
    
    Args:
        file_id: File identifier
        parser: PO file parser dependency
        
    Returns:
        File information and statistics
        
    Raises:
        HTTPException: If file not found
    """
    try:
        # Find file in upload directory
        upload_files = list(settings.upload_dir.glob(f"{file_id}_*"))
        
        if not upload_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        upload_path = upload_files[0]
        original_filename = upload_path.name[len(file_id) + 1:]  # Remove file_id prefix
        
        # Parse file for detailed info
        po_file = await parser.parse_file(str(upload_path))
        
        return SuccessResponse(
            message="File information retrieved",
            data={
                "file_id": file_id,
                "filename": original_filename,
                "file_size": upload_path.stat().st_size,
                "upload_path": str(upload_path),
                "statistics": parser.get_file_statistics(po_file),
                "metadata": po_file.metadata.dict()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info for {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get file information")


@router.delete("/upload/{file_id}")
async def delete_uploaded_file(file_id: str):
    """
    Delete an uploaded file.
    
    Args:
        file_id: File identifier
        
    Returns:
        Success response
        
    Raises:
        HTTPException: If file not found
    """
    try:
        # Find and delete file
        upload_files = list(settings.upload_dir.glob(f"{file_id}_*"))
        
        if not upload_files:
            raise HTTPException(status_code=404, detail="File not found")
        
        for file_path in upload_files:
            file_path.unlink()
            logger.info(f"Deleted uploaded file: {file_path}")
        
        return SuccessResponse(
            message=f"File {file_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")


# Background tasks
async def cleanup_file(file_path: Path):
    """Clean up a single file."""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up file {file_path}: {e}")


async def cleanup_old_files():
    """Clean up old uploaded files based on retention policy."""
    try:
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.now() - timedelta(days=settings.file_config.storage_retention_days)
        
        for file_path in settings.upload_dir.iterdir():
            if file_path.is_file():
                file_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_modified < cutoff_time:
                    file_path.unlink()
                    logger.info(f"Cleaned up old file: {file_path}")
                    
    except Exception as e:
        logger.error(f"Error during old file cleanup: {e}")


@router.get("/upload/stats")
async def get_upload_stats():
    """Get upload statistics."""
    try:
        upload_dir = settings.upload_dir
        
        if not upload_dir.exists():
            return SuccessResponse(
                message="Upload statistics",
                data={
                    "total_files": 0,
                    "total_size_bytes": 0,
                    "directory_exists": False
                }
            )
        
        files = list(upload_dir.iterdir())
        total_files = len([f for f in files if f.is_file()])
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        return SuccessResponse(
            message="Upload statistics",
            data={
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "directory_exists": True,
                "storage_path": str(upload_dir)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting upload stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get upload statistics") 