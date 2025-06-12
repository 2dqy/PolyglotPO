"""
Configuration management for the Translation Tool.
Handles environment variables, API settings, and application configuration.
"""

import os
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class DeepSeekConfig(BaseModel):
    """DeepSeek API configuration."""
    api_key: str = Field(..., description="DeepSeek API key")
    base_url: str = Field(default="https://api.deepseek.com/v1", description="DeepSeek API base URL")
    model: str = Field(default="deepseek-chat", description="DeepSeek model to use")
    max_tokens: int = Field(default=2048, description="Maximum tokens per request")
    temperature: float = Field(default=0.3, description="Translation temperature")
    timeout: int = Field(default=30, description="Request timeout in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, description="Delay between retries in seconds")
    rate_limit: int = Field(default=10, description="Requests per minute")


class FileConfig(BaseModel):
    """File handling configuration."""
    max_file_size: int = Field(default=50 * 1024 * 1024, description="Maximum file size in bytes (50MB)")
    allowed_extensions: List[str] = Field(default=[".po"], description="Allowed file extensions")
    upload_timeout: int = Field(default=300, description="Upload timeout in seconds")
    cleanup_interval: int = Field(default=3600, description="File cleanup interval in seconds")
    storage_retention_days: int = Field(default=7, description="Days to retain processed files")


class TranslationConfig(BaseModel):
    """Translation processing configuration."""
    concurrent_translations: int = Field(default=5, description="Max concurrent translation requests")
    batch_size: int = Field(default=10, description="Entries per translation batch")
    progress_update_interval: float = Field(default=1.0, description="Progress update interval in seconds")
    job_timeout: int = Field(default=1800, description="Job timeout in seconds (30 minutes)")


class Settings(BaseSettings):
    """Main application settings."""
    
    # Application settings
    app_name: str = Field(default="PolyglotPO", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=False, description="Auto-reload on changes")
    workers: int = Field(default=1, description="Number of worker processes")
    
    # Security settings
    secret_key: str = Field(default="your-secret-key-change-in-production", description="Secret key for sessions")
    allowed_hosts: List[str] = Field(default=["*"], description="Allowed hosts")
    
    # Storage paths
    base_dir: Path = Field(default=Path(__file__).parent.parent, description="Base directory")
    storage_dir: Optional[Path] = Field(default=None, description="Storage directory")
    upload_dir: Optional[Path] = Field(default=None, description="Upload directory")
    processed_dir: Optional[Path] = Field(default=None, description="Processed files directory")
    download_dir: Optional[Path] = Field(default=None, description="Download directory")
    
    # DeepSeek API Configuration (flattened for env vars)
    deepseek_api_key: str = Field(default="", description="DeepSeek API key")
    deepseek_base_url: str = Field(default="https://api.deepseek.com/v1", description="DeepSeek API base URL")
    deepseek_model: str = Field(default="deepseek-chat", description="DeepSeek model to use (points to V3-0324)")
    deepseek_max_tokens: int = Field(default=2048, description="Maximum tokens per request")
    deepseek_temperature: float = Field(default=0.3, description="Translation temperature (optimized for V3)")
    deepseek_timeout: int = Field(default=30, description="Request timeout in seconds")
    deepseek_max_retries: int = Field(default=3, description="Maximum retry attempts")
    deepseek_retry_delay: float = Field(default=1.0, description="Delay between retries in seconds")
    deepseek_rate_limit: int = Field(default=10, description="Requests per minute")
    
    # File Configuration (flattened for env vars)
    max_file_size: int = Field(default=50 * 1024 * 1024, description="Maximum file size in bytes (50MB)")
    storage_retention_days: int = Field(default=1, description="Days to retain processed files")
    cleanup_interval: int = Field(default=3600, description="File cleanup interval in seconds")
    
    # Translation Configuration (flattened for env vars)
    concurrent_translations: int = Field(default=5, description="Max concurrent translation requests")
    batch_size: int = Field(default=10, description="Entries per translation batch")
    job_timeout: int = Field(default=1800, description="Job timeout in seconds (30 minutes)")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # Database (for future expansion)
    database_url: str = Field(default="sqlite:///./translation_tool.db", description="Database URL")
    
    class Config:
        env_file = "../.env"  # Look in project root (one level up from src)
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "allow"  # Allow extra fields from env vars
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_directories()
    
    def _setup_directories(self) -> None:
        """Set up directory paths and create them if they don't exist."""
        if self.storage_dir is None:
            self.storage_dir = self.base_dir / "app" / "storage"
        
        if self.upload_dir is None:
            self.upload_dir = self.storage_dir / "uploads"
        
        if self.processed_dir is None:
            self.processed_dir = self.storage_dir / "processed"
        
        if self.download_dir is None:
            self.download_dir = self.storage_dir / "downloads"
        
        # Create directories
        for directory in [self.storage_dir, self.upload_dir, self.processed_dir, self.download_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def deepseek(self) -> DeepSeekConfig:
        """Get DeepSeek configuration."""
        return DeepSeekConfig(
            api_key=self.deepseek_api_key,
            base_url=self.deepseek_base_url,
            model=self.deepseek_model,
            max_tokens=self.deepseek_max_tokens,
            temperature=self.deepseek_temperature,
            timeout=self.deepseek_timeout,
            max_retries=self.deepseek_max_retries,
            retry_delay=self.deepseek_retry_delay,
            rate_limit=self.deepseek_rate_limit
        )
    
    @property
    def file_config(self) -> FileConfig:
        """Get file configuration."""
        return FileConfig(
            max_file_size=self.max_file_size,
            allowed_extensions=[".po"],
            upload_timeout=300,
            cleanup_interval=self.cleanup_interval,
            storage_retention_days=self.storage_retention_days
        )
    
    @property
    def translation_config(self) -> TranslationConfig:
        """Get translation configuration."""
        return TranslationConfig(
            concurrent_translations=self.concurrent_translations,
            batch_size=self.batch_size,
            progress_update_interval=1.0,
            job_timeout=self.job_timeout
        )


# Global settings instance
settings = Settings()


# Mock API functions for development/testing
class MockDeepSeekAPI:
    """Mock DeepSeek API for development and testing."""
    
    @staticmethod
    async def translate_text(text: str, target_language: str, source_language: str = "en") -> str:
        """
        Mock translation function.
        TODO: Replace with actual DeepSeek API integration.
        """
        # Simple mock translation - adds language prefix
        if not text.strip():
            return text
        
        language_prefixes = {
            "es": "[ES]",
            "fr": "[FR]",
            "de": "[DE]",
            "it": "[IT]",
            "pt": "[PT]",
            "ru": "[RU]",
            "ja": "[JA]",
            "ko": "[KO]",
            "zh": "[ZH]",
            "ar": "[AR]"
        }
        
        prefix = language_prefixes.get(target_language.lower(), f"[{target_language.upper()}]")
        return f"{prefix} {text}"
    
    @staticmethod
    async def get_supported_languages() -> List[str]:
        """
        Mock supported languages function.
        TODO: Replace with actual DeepSeek API call.
        """
        return [
            "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh", "ar",
            "nl", "sv", "no", "da", "fi", "pl", "cs", "hu", "ro", "bg"
        ]


# Language configuration
SUPPORTED_LANGUAGES = {
    "es": "Spanish",
    "fr": "French", 
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "nl": "Dutch",
    "sv": "Swedish",
    "no": "Norwegian", 
    "da": "Danish",
    "fi": "Finnish",
    "pl": "Polish",
    "cs": "Czech",
    "hu": "Hungarian",
    "ro": "Romanian",
    "bg": "Bulgarian"
}

# File type mappings
MIME_TYPES = {
    ".po": "application/x-gettext-translation",
    ".pot": "application/x-gettext-translation-template"
}

# Default endpoints (mock)
API_ENDPOINTS = {
    "deepseek_translate": "https://api.deepseek.com/v1/chat/completions",
    "deepseek_models": "https://api.deepseek.com/v1/models"
} 