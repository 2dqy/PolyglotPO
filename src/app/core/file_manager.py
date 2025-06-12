"""
File management utilities for the Translation Tool.
Handles file operations, storage, and cleanup.
"""

import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
import uuid

import aiofiles
import aiofiles.os
from fastapi import UploadFile
from loguru import logger

from ..config import settings
from ..utils.exceptions import StorageError, FileSizeExceededError, UnsupportedFileTypeError


class FileManager:
    """
    Manages file operations for the Translation Tool.
    Handles uploads, storage, downloads, and cleanup.
    """
    
    def __init__(self):
        self.upload_dir = settings.upload_dir
        self.processed_dir = settings.processed_dir
        self.download_dir = settings.download_dir
        self.max_file_size = settings.file_config.max_file_size
        self.allowed_extensions = settings.file_config.allowed_extensions
        self.retention_days = settings.file_config.storage_retention_days
    
    async def save_uploaded_file(self, file: UploadFile, job_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Save uploaded file to storage.
        
        Args:
            file: FastAPI UploadFile object
            job_id: Optional job ID for file organization
            
        Returns:
            Dict with file info (path, size, etc.)
        """
        if not job_id:
            job_id = str(uuid.uuid4())
        
        try:
            # Validate file
            await self._validate_file(file)
            
            # Create upload directory for this job
            job_upload_dir = self.upload_dir / job_id
            await self._ensure_directory(job_upload_dir)
            
            # Generate unique filename
            file_extension = Path(file.filename).suffix
            safe_filename = f"original{file_extension}"
            file_path = job_upload_dir / safe_filename
            
            # Save file
            file_size = await self._save_file_to_disk(file, file_path)
            
            file_info = {
                "job_id": job_id,
                "original_filename": file.filename,
                "file_path": str(file_path),
                "file_size": file_size,
                "uploaded_at": datetime.utcnow(),
                "file_extension": file_extension,
                "safe_filename": safe_filename
            }
            
            logger.info(f"File saved: {file.filename} -> {file_path} ({file_size} bytes)")
            
            return file_info
            
        except Exception as e:
            logger.error(f"Failed to save uploaded file {file.filename}: {e}")
            raise StorageError(f"Failed to save file: {str(e)}")
    
    async def _validate_file(self, file: UploadFile) -> None:
        """Validate uploaded file."""
        # Check file extension
        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in self.allowed_extensions:
            raise UnsupportedFileTypeError(
                f"File type {file_extension} not supported. "
                f"Allowed types: {', '.join(self.allowed_extensions)}"
            )
        
        # Check file size
        # Note: For UploadFile, size might not be available until read
        content = await file.read()
        file_size = len(content)
        await file.seek(0)  # Reset file pointer
        
        if file_size > self.max_file_size:
            raise FileSizeExceededError(
                f"File size ({file_size} bytes) exceeds maximum allowed "
                f"size ({self.max_file_size} bytes)"
            )
        
        # Check if file is empty
        if file_size == 0:
            raise StorageError("Empty file not allowed")
    
    async def _save_file_to_disk(self, file: UploadFile, file_path: Path) -> int:
        """Save file to disk and return file size."""
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                content = await file.read()
                await f.write(content)
                return len(content)
                
        except Exception as e:
            # Clean up partial file if it exists
            if file_path.exists():
                await aiofiles.os.remove(file_path)
            raise StorageError(f"Failed to write file to disk: {str(e)}")
    
    async def create_processed_file(
        self, 
        job_id: str, 
        content: str, 
        filename: str,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Create processed (translated) file.
        
        Args:
            job_id: Translation job ID
            content: Translated file content
            filename: Original filename
            target_language: Target language code
            
        Returns:
            Dict with processed file info
        """
        try:
            # Create processed directory for this job
            job_processed_dir = self.processed_dir / job_id
            await self._ensure_directory(job_processed_dir)
            
            # Generate processed filename
            original_name = Path(filename).stem
            file_extension = Path(filename).suffix
            processed_filename = f"{original_name}_{target_language}{file_extension}"
            processed_path = job_processed_dir / processed_filename
            
            # Save processed content
            async with aiofiles.open(processed_path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            # Get file size
            file_size = len(content.encode('utf-8'))
            
            file_info = {
                "job_id": job_id,
                "processed_filename": processed_filename,
                "file_path": str(processed_path),
                "file_size": file_size,
                "target_language": target_language,
                "processed_at": datetime.utcnow()
            }
            
            logger.info(f"Processed file created: {processed_filename} ({file_size} bytes)")
            
            return file_info
            
        except Exception as e:
            logger.error(f"Failed to create processed file for job {job_id}: {e}")
            raise StorageError(f"Failed to create processed file: {str(e)}")
    
    async def prepare_download_file(self, job_id: str, processed_file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare file for download by copying to download directory.
        
        Args:
            job_id: Translation job ID
            processed_file_info: Processed file information
            
        Returns:
            Dict with download file info
        """
        try:
            # Create download directory for this job
            job_download_dir = self.download_dir / job_id
            await self._ensure_directory(job_download_dir)
            
            # Source and destination paths
            source_path = Path(processed_file_info["file_path"])
            download_filename = processed_file_info["processed_filename"]
            download_path = job_download_dir / download_filename
            
            # Copy file to download directory
            shutil.copy2(source_path, download_path)
            
            download_info = {
                "job_id": job_id,
                "download_filename": download_filename,
                "download_path": str(download_path),
                "file_size": processed_file_info["file_size"],
                "prepared_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=self.retention_days)
            }
            
            logger.info(f"Download file prepared: {download_filename}")
            
            return download_info
            
        except Exception as e:
            logger.error(f"Failed to prepare download file for job {job_id}: {e}")
            raise StorageError(f"Failed to prepare download file: {str(e)}")
    
    async def get_file_content(self, file_path: str) -> str:
        """
        Read file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            File content as string
        """
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
                
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise StorageError(f"Failed to read file: {str(e)}")
    
    async def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get file information.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dict with file info
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise StorageError(f"File not found: {file_path}")
            
            stat = await aiofiles.os.stat(file_path)
            
            return {
                "file_path": str(path),
                "filename": path.name,
                "file_size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime),
                "modified_at": datetime.fromtimestamp(stat.st_mtime),
                "exists": True
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            raise StorageError(f"Failed to get file info: {str(e)}")
    
    async def cleanup_job_files(self, job_id: str) -> None:
        """
        Clean up all files for a job.
        
        Args:
            job_id: Translation job ID
        """
        try:
            # Directories to clean up
            directories = [
                self.upload_dir / job_id,
                self.processed_dir / job_id,
                self.download_dir / job_id
            ]
            
            for directory in directories:
                if directory.exists():
                    shutil.rmtree(directory)
                    logger.info(f"Cleaned up directory: {directory}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup files for job {job_id}: {e}")
            # Don't raise exception for cleanup failures
    
    async def cleanup_old_files(self) -> None:
        """Clean up old files based on retention policy."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            # Clean up old job directories
            for base_dir in [self.upload_dir, self.processed_dir, self.download_dir]:
                if not base_dir.exists():
                    continue
                
                for job_dir in base_dir.iterdir():
                    if not job_dir.is_dir():
                        continue
                    
                    # Check directory age
                    stat = await aiofiles.os.stat(job_dir)
                    created_at = datetime.fromtimestamp(stat.st_ctime)
                    
                    if created_at < cutoff_date:
                        shutil.rmtree(job_dir)
                        logger.info(f"Cleaned up old directory: {job_dir}")
            
            logger.info("Old file cleanup completed")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            # Don't raise exception for cleanup failures
    
    async def get_job_files(self, job_id: str) -> Dict[str, Any]:
        """
        Get all files for a job.
        
        Args:
            job_id: Translation job ID (or file_id for uploads)
            
        Returns:
            Dict with file paths and info
        """
        try:
            files = {
                "upload": None,
                "processed": None,
                "download": None
            }
            
            # Check for uploaded files (saved as {file_id}_{filename})
            upload_files = list(self.upload_dir.glob(f"{job_id}_*"))
            if upload_files:
                files["upload"] = str(upload_files[0])
            else:
                # Also check subdirectory structure (for backward compatibility)
                upload_dir = self.upload_dir / job_id
                if upload_dir.exists():
                    upload_files = list(upload_dir.glob("*"))
                    if upload_files:
                        files["upload"] = str(upload_files[0])
            
            # Check processed directory
            processed_dir = self.processed_dir / job_id
            if processed_dir.exists():
                processed_files = list(processed_dir.glob("*"))
                if processed_files:
                    files["processed"] = str(processed_files[0])
            
            # Check download directory
            download_dir = self.download_dir / job_id
            if download_dir.exists():
                download_files = list(download_dir.glob("*"))
                if download_files:
                    files["download"] = str(download_files[0])
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to get job files for {job_id}: {e}")
            raise StorageError(f"Failed to get job files: {str(e)}")
    
    async def _ensure_directory(self, directory: Path) -> None:
        """Ensure directory exists."""
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise StorageError(f"Failed to create directory {directory}: {str(e)}")


# Global file manager instance
_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    """Get or create file manager instance."""
    global _file_manager
    
    if _file_manager is None:
        _file_manager = FileManager()
    
    return _file_manager


async def start_cleanup_task():
    """Start background task for file cleanup."""
    file_manager = get_file_manager()
    cleanup_interval = settings.file_config.cleanup_interval
    
    while True:
        try:
            await asyncio.sleep(cleanup_interval)
            await file_manager.cleanup_old_files()
        except Exception as e:
            logger.error(f"File cleanup task error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying 