"""
API request and response models for the Translation Tool.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SuccessResponse(BaseModel):
    """Generic success response model."""
    
    success: bool = Field(default=True, description="Success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(BaseModel):
    """Generic error response model."""
    
    success: bool = Field(default=False, description="Success status")
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class FileUploadResponse(BaseModel):
    """Response model for file upload."""
    
    success: bool = Field(default=True, description="Upload success status")
    filename: str = Field(..., description="Original filename")
    file_id: str = Field(..., description="Unique file identifier")
    file_size: int = Field(..., description="File size in bytes")
    upload_path: str = Field(..., description="Upload path")
    
    # File validation results
    is_valid: bool = Field(..., description="File validation status")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    
    # PO file statistics
    total_entries: int = Field(default=0, description="Total PO entries")
    translated_entries: int = Field(default=0, description="Already translated entries")
    untranslated_entries: int = Field(default=0, description="Untranslated entries")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Upload timestamp")


class LanguageInfo(BaseModel):
    """Language information model."""
    
    code: str = Field(..., description="Language code (e.g., 'es', 'fr')")
    name: str = Field(..., description="Language name (e.g., 'Spanish', 'French')")
    native_name: Optional[str] = Field(None, description="Native language name")
    is_supported: bool = Field(default=True, description="Whether language is supported for translation")


class TranslationRequest(BaseModel):
    """Request model for starting translation."""
    
    file_id: str = Field(..., description="File identifier from upload")
    target_language: str = Field(..., description="Target language code")
    source_language: str = Field(default="en", description="Source language code") 
    
    # Translation options
    preserve_formatting: bool = Field(default=True, description="Preserve text formatting")
    translate_empty: bool = Field(default=False, description="Translate empty strings")
    overwrite_existing: bool = Field(default=False, description="Overwrite existing translations")
    
    # Processing options
    batch_size: Optional[int] = Field(None, description="Custom batch size for processing")


class JobStatusResponse(BaseModel):
    """Response model for job status queries."""
    
    job_id: str = Field(..., description="Job identifier")
    status: str = Field(..., description="Current job status")
    filename: str = Field(..., description="Original filename")
    
    # Progress information
    progress_percentage: float = Field(..., description="Completion percentage")
    total_entries: int = Field(..., description="Total entries to process")
    processed_entries: int = Field(..., description="Entries processed")
    successful_translations: int = Field(..., description="Successful translations")
    failed_translations: int = Field(..., description="Failed translations")
    
    # Time information
    created_at: datetime = Field(..., description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion")
    duration_seconds: Optional[int] = Field(None, description="Job duration")
    
    # Error information
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    # Results
    download_url: Optional[str] = Field(None, description="Download URL when completed")


class JobListResponse(BaseModel):
    """Response model for job listing."""
    
    jobs: List[JobStatusResponse] = Field(..., description="List of jobs")
    total_count: int = Field(..., description="Total number of jobs")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=10, description="Items per page")
    has_next: bool = Field(default=False, description="Whether there are more pages")


class DownloadResponse(BaseModel):
    """Response model for download requests."""
    
    job_id: str = Field(..., description="Job identifier")
    filename: str = Field(..., description="Download filename")
    file_size: int = Field(..., description="File size in bytes")
    download_url: str = Field(..., description="Download URL")
    expires_at: datetime = Field(..., description="Download URL expiration")


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(default="healthy", description="Service status")
    version: str = Field(..., description="Application version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    
    # Service checks
    database_status: str = Field(default="ok", description="Database status")
    storage_status: str = Field(default="ok", description="Storage status") 
    api_status: str = Field(default="ok", description="Translation API status")
    
    # System info
    uptime_seconds: Optional[int] = Field(None, description="Service uptime")
    active_jobs: int = Field(default=0, description="Currently active jobs")
    total_jobs_processed: int = Field(default=0, description="Total jobs processed")


class StatisticsResponse(BaseModel):
    """Application statistics response."""
    
    # Job statistics
    total_jobs: int = Field(default=0, description="Total jobs created")
    completed_jobs: int = Field(default=0, description="Completed jobs")
    failed_jobs: int = Field(default=0, description="Failed jobs")
    active_jobs: int = Field(default=0, description="Currently active jobs")
    
    # Translation statistics
    total_translations: int = Field(default=0, description="Total translations performed")
    successful_translations: int = Field(default=0, description="Successful translations")
    failed_translations: int = Field(default=0, description="Failed translations")
    
    # File statistics
    total_files_processed: int = Field(default=0, description="Total files processed")
    total_entries_processed: int = Field(default=0, description="Total entries processed")
    
    # Performance metrics
    average_job_duration: Optional[float] = Field(None, description="Average job duration in seconds")
    translations_per_minute: Optional[float] = Field(None, description="Average translations per minute")
    
    # Language statistics
    most_common_source_languages: List[Dict[str, Any]] = Field(default_factory=list)
    most_common_target_languages: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Time range
    from_date: Optional[datetime] = Field(None, description="Statistics from date")
    to_date: Optional[datetime] = Field(None, description="Statistics to date")
    
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Statistics timestamp")


class ValidationErrorResponse(BaseModel):
    """Validation error response model."""
    
    success: bool = Field(default=False, description="Success status")
    error: str = Field(default="Validation Error", description="Error type")
    validation_errors: List[Dict[str, Any]] = Field(..., description="Detailed validation errors")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp") 