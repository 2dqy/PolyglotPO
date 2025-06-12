"""
Models package for the Translation Tool.
Contains Pydantic models for API requests/responses and data structures.
"""

from .po_models import POEntry, POFile, POFileMetadata
from .translation_models import (
    TranslationJob, 
    TranslationJobCreate, 
    TranslationJobResponse,
    TranslationProgress,
    TranslationStatus
)
from .api_models import (
    FileUploadResponse,
    ErrorResponse,
    SuccessResponse,
    LanguageInfo
)

__all__ = [
    # PO file models
    "POEntry",
    "POFile", 
    "POFileMetadata",
    
    # Translation models
    "TranslationJob",
    "TranslationJobCreate",
    "TranslationJobResponse", 
    "TranslationProgress",
    "TranslationStatus",
    
    # API models
    "FileUploadResponse",
    "ErrorResponse",
    "SuccessResponse",
    "LanguageInfo"
] 