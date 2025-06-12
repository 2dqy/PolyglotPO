"""
Custom exceptions for the Translation Tool.
Provides specific error types for better error handling and user feedback.
"""

from typing import Optional, Any, Dict


class TranslationToolError(Exception):
    """Base exception for all Translation Tool errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}


class FileProcessingError(TranslationToolError):
    """Raised when file processing fails."""
    pass


class InvalidPOFileError(FileProcessingError):
    """Raised when PO file is invalid or corrupted."""
    pass


class FileSizeExceededError(FileProcessingError):
    """Raised when uploaded file exceeds size limit."""
    pass


class UnsupportedFileTypeError(FileProcessingError):
    """Raised when file type is not supported."""
    pass


class TranslationAPIError(TranslationToolError):
    """Raised when translation API calls fail."""
    pass


class RateLimitError(TranslationAPIError):
    """Raised when API rate limit is exceeded."""
    pass


class TranslationServiceError(TranslationToolError):
    """Raised when translation service encounters errors."""
    pass


class JobNotFoundError(TranslationToolError):
    """Raised when translation job is not found."""
    pass


class JobProcessingError(TranslationToolError):
    """Raised when job processing fails."""
    pass


class StorageError(TranslationToolError):
    """Raised when file storage operations fail."""
    pass


class ValidationError(TranslationToolError):
    """Raised when input validation fails."""
    pass


class ConfigurationError(TranslationToolError):
    """Raised when configuration is invalid."""
    pass


class LanguageNotSupportedError(TranslationToolError):
    """Raised when requested language is not supported."""
    pass


# HTTP Exception mappings for FastAPI
ERROR_HTTP_MAPPINGS = {
    FileProcessingError: 400,
    InvalidPOFileError: 400,
    FileSizeExceededError: 413,
    UnsupportedFileTypeError: 415,
    ValidationError: 422,
    JobNotFoundError: 404,
    RateLimitError: 429,
    TranslationAPIError: 502,
    TranslationServiceError: 500,
    JobProcessingError: 500,
    StorageError: 500,
    ConfigurationError: 500,
    LanguageNotSupportedError: 400,
} 