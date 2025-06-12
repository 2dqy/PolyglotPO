"""
Pydantic models for translation jobs and progress tracking.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator


class TranslationStatus(str, Enum):
    """Translation job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranslationProgress(BaseModel):
    """Real-time translation progress information."""
    
    job_id: str = Field(..., description="Translation job ID")
    status: TranslationStatus = Field(default=TranslationStatus.PENDING, description="Current status")
    
    # Progress metrics
    total_entries: int = Field(default=0, description="Total entries to translate")
    processed_entries: int = Field(default=0, description="Entries processed so far")
    successful_translations: int = Field(default=0, description="Successful translations")
    failed_translations: int = Field(default=0, description="Failed translations")
    
    # Time tracking
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    
    # Error information
    current_error: Optional[str] = Field(None, description="Current error message")
    error_count: int = Field(default=0, description="Total number of errors")
    
    # Performance metrics
    translations_per_minute: float = Field(default=0.0, description="Translation rate")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @validator('processed_entries')
    def processed_not_exceed_total(cls, v, values):
        """Ensure processed entries don't exceed total."""
        total = values.get('total_entries', 0)
        return min(v, total)
    
    def get_progress_percentage(self) -> float:
        """Calculate progress percentage."""
        if self.total_entries == 0:
            return 0.0
        return (self.processed_entries / self.total_entries) * 100
    
    def get_success_rate(self) -> float:
        """Calculate translation success rate."""
        if self.processed_entries == 0:
            return 0.0
        return (self.successful_translations / self.processed_entries) * 100
    
    def get_estimated_time_remaining(self) -> Optional[int]:
        """Estimate time remaining in seconds."""
        if not self.started_at or self.translations_per_minute == 0:
            return None
        
        remaining_entries = self.total_entries - self.processed_entries
        if remaining_entries <= 0:
            return 0
        
        minutes_remaining = remaining_entries / self.translations_per_minute
        return int(minutes_remaining * 60)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with calculated fields."""
        data = self.dict()
        data.update({
            "progress_percentage": self.get_progress_percentage(),
            "success_rate": self.get_success_rate(),
            "estimated_time_remaining": self.get_estimated_time_remaining()
        })
        return data


class TranslationJobCreate(BaseModel):
    """Request model for creating a translation job."""
    
    file_id: str = Field(..., description="File ID from upload")
    filename: str = Field(..., description="Original filename")
    target_language: str = Field(..., description="Target language code")
    source_language: str = Field(default="en", description="Source language code")
    
    # Optional parameters
    preserve_formatting: bool = Field(default=True, description="Preserve text formatting")
    translate_empty: bool = Field(default=False, description="Translate empty strings")
    overwrite_existing: bool = Field(default=False, description="Overwrite existing translations")
    
    @validator('target_language', 'source_language')
    def validate_language_codes(cls, v):
        """Validate language codes are not empty."""
        if not v or not v.strip():
            raise ValueError("Language code cannot be empty")
        return v.strip()  # Remove only whitespace, preserve case


class TranslationJob(BaseModel):
    """Complete translation job model."""
    
    # Job identification
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique job ID")
    
    # File information
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Path to uploaded file")
    file_size: int = Field(..., description="File size in bytes")
    
    # Translation parameters
    source_language: str = Field(default="en", description="Source language code")
    target_language: str = Field(..., description="Target language code")
    
    # Job configuration
    preserve_formatting: bool = Field(default=True, description="Preserve text formatting")
    translate_empty: bool = Field(default=False, description="Translate empty strings")
    overwrite_existing: bool = Field(default=False, description="Overwrite existing translations")
    
    # Job status and progress
    status: TranslationStatus = Field(default=TranslationStatus.PENDING, description="Job status")
    progress: Optional[TranslationProgress] = Field(default=None, description="Progress information")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Processing start time")
    completed_at: Optional[datetime] = Field(None, description="Processing completion time")
    
    # Results
    output_file_path: Optional[str] = Field(None, description="Path to translated file")
    download_url: Optional[str] = Field(None, description="Download URL")
    
    # Error handling
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @validator('progress', always=True)
    def create_progress(cls, v, values):
        """Initialize progress if not provided."""
        if v is None:
            job_id = values.get('job_id', str(uuid.uuid4()))
            return TranslationProgress(job_id=job_id)
        return v
    
    def update_status(self, status: TranslationStatus, error_message: Optional[str] = None):
        """Update job status with timestamp."""
        self.status = status
        self.progress.status = status
        
        if status == TranslationStatus.PROCESSING and not self.started_at:
            self.started_at = datetime.utcnow()
            self.progress.started_at = self.started_at
        
        elif status in [TranslationStatus.COMPLETED, TranslationStatus.FAILED, TranslationStatus.CANCELLED]:
            self.completed_at = datetime.utcnow()
            self.progress.completed_at = self.completed_at
        
        if error_message:
            self.error_message = error_message
            self.progress.current_error = error_message
    
    def get_duration(self) -> Optional[int]:
        """Get job duration in seconds."""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.utcnow()
        return int((end_time - self.started_at).total_seconds())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        data = self.dict()
        data['duration_seconds'] = self.get_duration()
        return data


class TranslationJobResponse(BaseModel):
    """API response model for translation jobs."""
    
    job_id: str = Field(..., description="Job ID")
    status: TranslationStatus = Field(..., description="Job status")
    filename: str = Field(..., description="Original filename")
    
    # Language info
    source_language: str = Field(..., description="Source language")
    target_language: str = Field(..., description="Target language")
    
    # Progress summary
    progress_percentage: float = Field(..., description="Progress percentage")
    total_entries: int = Field(..., description="Total entries")
    processed_entries: int = Field(..., description="Processed entries")
    
    # Timing
    created_at: datetime = Field(..., description="Creation timestamp")
    duration_seconds: Optional[int] = Field(None, description="Duration in seconds")
    
    # Results
    download_url: Optional[str] = Field(None, description="Download URL if completed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @classmethod
    def from_translation_job(cls, job: TranslationJob) -> "TranslationJobResponse":
        """Create response from TranslationJob."""
        # Ensure progress is properly initialized
        if job.progress is None or not isinstance(job.progress, TranslationProgress):
            progress = TranslationProgress(job_id=job.job_id)
        else:
            progress = job.progress
            
        return cls(
            job_id=job.job_id,
            status=job.status,
            filename=job.filename,
            source_language=job.source_language,
            target_language=job.target_language,
            progress_percentage=progress.get_progress_percentage(),
            total_entries=progress.total_entries,
            processed_entries=progress.processed_entries,
            created_at=job.created_at,
            duration_seconds=job.get_duration(),
            download_url=job.download_url,
            error_message=job.error_message
        )


class TranslationBatch(BaseModel):
    """Model for batch translation processing."""
    
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Batch ID")
    job_id: str = Field(..., description="Parent job ID")
    entries: List[Dict[str, Any]] = Field(..., description="Entries to translate")
    
    # Batch status
    status: TranslationStatus = Field(default=TranslationStatus.PENDING, description="Batch status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation time")
    
    # Results
    translated_entries: List[Dict[str, Any]] = Field(default_factory=list, description="Translated entries")
    failed_entries: List[Dict[str, Any]] = Field(default_factory=list, description="Failed entries")
    
    def get_success_count(self) -> int:
        """Get number of successful translations."""
        return len(self.translated_entries)
    
    def get_failure_count(self) -> int:
        """Get number of failed translations."""
        return len(self.failed_entries) 