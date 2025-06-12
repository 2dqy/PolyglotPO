"""
Helper utilities for the Translation Tool.
Provides common utility functions for formatting, calculations, and other operations.
"""

import asyncio
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

from loguru import logger


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: File size in bytes
        
    Returns:
        Formatted file size string
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def format_duration(seconds: Union[int, float]) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def format_timestamp(timestamp: datetime, relative: bool = False) -> str:
    """
    Format timestamp for display.
    
    Args:
        timestamp: Datetime to format
        relative: Whether to show relative time (e.g., "2 minutes ago")
        
    Returns:
        Formatted timestamp string
    """
    if relative:
        return format_time_ago(timestamp)
    else:
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def format_time_ago(timestamp: datetime) -> str:
    """
    Format timestamp as relative time (e.g., "2 minutes ago").
    
    Args:
        timestamp: Datetime to format
        
    Returns:
        Relative time string
    """
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff.total_seconds() < 60:
        return "just now"
    elif diff.total_seconds() < 3600:
        minutes = int(diff.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif diff.total_seconds() < 86400:
        hours = int(diff.total_seconds() / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = diff.days
        return f"{days} day{'s' if days != 1 else ''} ago"


def calculate_eta(processed: int, total: int, start_time: datetime) -> Optional[datetime]:
    """
    Calculate estimated time of arrival for a process.
    
    Args:
        processed: Number of items processed
        total: Total number of items
        start_time: When the process started
        
    Returns:
        Estimated completion time or None if not calculable
    """
    if processed <= 0 or total <= 0 or processed >= total:
        return None
    
    elapsed = (datetime.utcnow() - start_time).total_seconds()
    
    if elapsed <= 0:
        return None
    
    rate = processed / elapsed  # items per second
    remaining = total - processed
    eta_seconds = remaining / rate
    
    return datetime.utcnow() + timedelta(seconds=eta_seconds)


def generate_job_id(prefix: str = "") -> str:
    """
    Generate a unique job ID.
    
    Args:
        prefix: Optional prefix for the job ID
        
    Returns:
        Unique job ID string
    """
    import uuid
    
    job_id = str(uuid.uuid4())
    
    if prefix:
        return f"{prefix}-{job_id}"
    else:
        return job_id


def generate_file_hash(file_path: Union[str, Path], algorithm: str = "md5") -> str:
    """
    Generate hash for a file.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm to use (md5, sha1, sha256)
        
    Returns:
        File hash string
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    hash_obj = hashlib.new(algorithm)
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
    
    return hash_obj.hexdigest()


def safe_divide(numerator: Union[int, float], denominator: Union[int, float], default: float = 0.0) -> float:
    """
    Safely divide two numbers, avoiding division by zero.
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Default value if division by zero
        
    Returns:
        Division result or default value
    """
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ZeroDivisionError):
        return default


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate string to maximum length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating
        
    Returns:
        Truncated string
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_language_header(header: str) -> Dict[str, str]:
    """
    Parse language header from PO file.
    
    Args:
        header: Language header string
        
    Returns:
        Dictionary of parsed header fields
    """
    result = {}
    
    for line in header.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            result[key.strip()] = value.strip()
    
    return result


def merge_dicts(*dicts: Dict[str, Any], deep: bool = False) -> Dict[str, Any]:
    """
    Merge multiple dictionaries.
    
    Args:
        *dicts: Dictionaries to merge
        deep: Whether to perform deep merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    
    for d in dicts:
        if deep:
            for key, value in d.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value, deep=True)
                else:
                    result[key] = value
        else:
            result.update(d)
    
    return result


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split list into chunks of specified size.
    
    Args:
        lst: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    if chunk_size <= 0:
        raise ValueError("Chunk size must be positive")
    
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_list(nested_list: List[List[Any]]) -> List[Any]:
    """
    Flatten a nested list.
    
    Args:
        nested_list: Nested list to flatten
        
    Returns:
        Flattened list
    """
    result = []
    for item in nested_list:
        if isinstance(item, list):
            result.extend(flatten_list(item))
        else:
            result.append(item)
    return result


async def retry_async(
    func, 
    *args, 
    max_retries: int = 3, 
    delay: float = 1.0, 
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    **kwargs
) -> Any:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        *args: Function arguments
        max_retries: Maximum number of retries
        delay: Initial delay between retries
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            
            if attempt < max_retries:
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s...")
                await asyncio.sleep(current_delay)
                current_delay *= backoff_factor
            else:
                logger.error(f"All {max_retries + 1} attempts failed")
                break
    
    raise last_exception


def create_progress_callback(job_id: str, total_items: int):
    """
    Create a progress callback function for tracking job progress.
    
    Args:
        job_id: Job ID for tracking
        total_items: Total number of items to process
        
    Returns:
        Progress callback function
    """
    start_time = datetime.utcnow()
    
    async def progress_callback(current_item: int, message: str = "Processing..."):
        progress_percentage = min(int((current_item / total_items) * 100), 100)
        
        # Calculate ETA
        eta = calculate_eta(current_item, total_items, start_time)
        eta_str = format_timestamp(eta) if eta else "Unknown"
        
        logger.info(f"Job {job_id}: {progress_percentage}% ({current_item}/{total_items}) - {message} - ETA: {eta_str}")
        
        return {
            "job_id": job_id,
            "progress": progress_percentage,
            "current": current_item,
            "total": total_items,
            "message": message,
            "eta": eta_str
        }
    
    return progress_callback


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.
    
    Args:
        text: Text to normalize
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return text
    
    # Replace multiple whitespace characters with single space
    import re
    return re.sub(r'\s+', ' ', text.strip())


def extract_po_statistics(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Extract statistics from PO file entries.
    
    Args:
        entries: List of PO entries
        
    Returns:
        Dictionary with statistics
    """
    stats = {
        "total": len(entries),
        "translated": 0,
        "untranslated": 0,
        "fuzzy": 0,
        "obsolete": 0
    }
    
    for entry in entries:
        if entry.get("obsolete"):
            stats["obsolete"] += 1
        elif "fuzzy" in entry.get("flags", []):
            stats["fuzzy"] += 1
        elif entry.get("msgstr"):
            stats["translated"] += 1
        else:
            stats["untranslated"] += 1
    
    return stats


class Timer:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str = "Operation"):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = self.end_time - self.start_time
        logger.info(f"{self.operation_name} completed in {format_duration(duration)}")
    
    @property
    def duration(self) -> Optional[float]:
        """Get the duration of the timed operation."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None 