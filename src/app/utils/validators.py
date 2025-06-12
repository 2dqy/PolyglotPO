"""
Input validation utilities for the Translation Tool.
Provides validators for files, languages, and other inputs.
"""

import re
from pathlib import Path
from typing import List, Optional, Union, Tuple

from ..config import SUPPORTED_LANGUAGES, settings
from .exceptions import ValidationError, UnsupportedFileTypeError, FileSizeExceededError


def validate_po_file_name(filename: str) -> bool:
    """
    Validate PO file name format.
    
    Args:
        filename: File name to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not filename:
        return False
    
    # Check extension
    return filename.lower().endswith('.po')


def validate_file_size(file_size: int, max_size: Optional[int] = None) -> None:
    """
    Validate file size against limits.
    
    Args:
        file_size: File size in bytes
        max_size: Maximum allowed size (defaults to config)
        
    Raises:
        FileSizeExceededError: If file is too large
    """
    if max_size is None:
        max_size = settings.file_config.max_file_size
    
    if file_size > max_size:
        raise FileSizeExceededError(
            f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
        )


def validate_language_code(language_code: str, supported_languages: Optional[List[str]] = None) -> None:
    """
    Validate language code.
    
    Args:
        language_code: Language code to validate
        supported_languages: List of supported languages (defaults to config)
        
    Raises:
        ValidationError: If language code is invalid
    """
    if not language_code:
        raise ValidationError("Language code cannot be empty")
    
    if supported_languages is None:
        supported_languages = list(SUPPORTED_LANGUAGES.keys())
    
    # Allow 'auto' for source language detection
    if language_code == "auto":
        return
    
    if language_code not in supported_languages:
        raise ValidationError(
            f"Unsupported language code: {language_code}. "
            f"Supported languages: {', '.join(supported_languages)}"
        )


def validate_job_id(job_id: str) -> None:
    """
    Validate job ID format.
    
    Args:
        job_id: Job ID to validate
        
    Raises:
        ValidationError: If job ID format is invalid
    """
    if not job_id:
        raise ValidationError("Job ID cannot be empty")
    
    # Job IDs should be alphanumeric with hyphens and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', job_id):
        raise ValidationError(
            "Job ID must contain only alphanumeric characters, hyphens, and underscores"
        )
    
    # Check length
    if len(job_id) < 3 or len(job_id) > 100:
        raise ValidationError("Job ID must be between 3 and 100 characters")


def validate_pagination_params(limit: int, offset: int) -> Tuple[int, int]:
    """
    Validate and normalize pagination parameters.
    
    Args:
        limit: Maximum number of items to return
        offset: Number of items to skip
        
    Returns:
        Tuple of (validated_limit, validated_offset)
        
    Raises:
        ValidationError: If parameters are invalid
    """
    # Validate limit
    if limit < 1:
        limit = 1
    elif limit > 100:
        limit = 100
    
    # Validate offset
    if offset < 0:
        offset = 0
    
    return limit, offset


def validate_sort_params(sort_by: str, sort_order: str, allowed_fields: List[str]) -> Tuple[str, str]:
    """
    Validate sorting parameters.
    
    Args:
        sort_by: Field to sort by
        sort_order: Sort order (asc/desc)
        allowed_fields: List of allowed sort fields
        
    Returns:
        Tuple of (validated_sort_by, validated_sort_order)
        
    Raises:
        ValidationError: If parameters are invalid
    """
    # Validate sort field
    if sort_by not in allowed_fields:
        sort_by = allowed_fields[0] if allowed_fields else "created_at"
    
    # Validate sort order
    if sort_order.lower() not in ["asc", "desc"]:
        sort_order = "desc"
    else:
        sort_order = sort_order.lower()
    
    return sort_by, sort_order


def validate_text_content(text: str, max_length: int = 10000) -> None:
    """
    Validate text content for translation.
    
    Args:
        text: Text to validate
        max_length: Maximum allowed length
        
    Raises:
        ValidationError: If text is invalid
    """
    if text is None:
        raise ValidationError("Text cannot be None")
    
    if len(text) > max_length:
        raise ValidationError(f"Text length ({len(text)}) exceeds maximum ({max_length})")


def validate_po_content_basic(content: str) -> None:
    """
    Basic validation of PO file content.
    
    Args:
        content: PO file content to validate
        
    Raises:
        ValidationError: If content is invalid
    """
    if not content or not content.strip():
        raise ValidationError("PO file content cannot be empty")
    
    # Check for basic PO file markers
    required_markers = ["msgid", "msgstr"]
    
    for marker in required_markers:
        if marker not in content:
            raise ValidationError(f"Invalid PO file: missing '{marker}' entries")


def validate_po_entry_content(msgid: str, msgstr: str = "") -> Tuple[bool, List[str]]:
    """
    Validate PO entry content for special characters and formatting.
    
    Args:
        msgid: Source message ID
        msgstr: Translated message string
        
    Returns:
        Tuple of (is_valid, warning_messages)
    """
    warnings = []
    
    # Define patterns for special content
    special_patterns = {
        # Variable patterns
        'at_variables': r'@\w+',           # @count, @name, @variable
        'percent_variables': r'%\w+',      # %username, %count
        'dollar_variables': r'\$\w+',      # $variable
        'curly_variables': r'\{\{\s*\w+\s*\}\}',  # {{ variable }}
        'angular_variables': r'\{\{\s*[^}]+\s*\}\}',  # Angular-style
        
        # HTML and markup
        'html_tags': r'<[^>]*>',           # <div>, <a href="...">
        'html_entities': r'&[a-zA-Z]+;',   # &nbsp;, &lt;, &gt;
        'numeric_entities': r'&#\d+;',     # &#160;
        
        # Programming constructs  
        'function_calls': r'\w+\([^)]*\)',  # function(), path()
        'array_access': r'\w+\[[^\]]*\]',   # array[key]
        'object_notation': r'\w+\.\w+',     # object.property
        
        # Format specifiers
        'printf_specs': r'%[sdifcbxXoueEgGdhlL]',  # %s, %d, %f etc
        'numbered_specs': r'%\d+\$[sdifcbxXoueEgGdhlL]',  # %1$s, %2$d
        
        # URLs and paths
        'urls': r'https?://[^\s<>"]+',     # HTTP URLs
        'file_paths': r'[/\\][\w/\\.-]+',  # File paths
        'drupal_paths': r'\w+/\w+',        # Drupal-style paths
        
        # Special punctuation
        'quotes': r'[""''`´]',             # Various quote styles  
        'dashes': r'[–—]',                 # En/em dashes
        'ellipsis': r'…',                  # Ellipsis character
    }
    
    # Count occurrences of each pattern type
    msgid_patterns = {}
    msgstr_patterns = {}
    
    for pattern_name, pattern in special_patterns.items():
        msgid_matches = re.findall(pattern, msgid, re.IGNORECASE | re.MULTILINE)
        msgstr_matches = re.findall(pattern, msgstr, re.IGNORECASE | re.MULTILINE) if msgstr else []
        
        msgid_patterns[pattern_name] = msgid_matches
        msgstr_patterns[pattern_name] = msgstr_matches
    
    # Validation rules
    
    # 1. Critical patterns must be preserved exactly
    critical_patterns = ['at_variables', 'percent_variables', 'printf_specs', 'numbered_specs']
    
    for pattern_name in critical_patterns:
        source_items = msgid_patterns[pattern_name]
        target_items = msgstr_patterns[pattern_name]
        
        if msgstr and set(source_items) != set(target_items):
            missing = set(source_items) - set(target_items)
            extra = set(target_items) - set(source_items)
            
            if missing:
                warnings.append(f"Missing critical placeholders in translation: {', '.join(missing)}")
            if extra:
                warnings.append(f"Extra placeholders in translation: {', '.join(extra)}")
    
    # 2. HTML tags should be preserved
    source_html = msgid_patterns['html_tags']
    target_html = msgstr_patterns['html_tags']
    
    if msgstr and source_html and not target_html:
        warnings.append("HTML tags present in source but missing in translation")
    
    # 3. Check for potentially problematic content
    problematic_patterns = {
        'script_tags': r'<script[^>]*>',
        'style_tags': r'<style[^>]*>',
        'javascript': r'javascript:',
        'data_urls': r'data:',
    }
    
    for pattern_name, pattern in problematic_patterns.items():
        if re.search(pattern, msgid, re.IGNORECASE):
            warnings.append(f"Potentially unsafe content detected: {pattern_name}")
    
    # 4. Check for encoding issues
    encoding_issues = []
    
    # Check for mixed encodings
    try:
        msgid.encode('ascii')
    except UnicodeEncodeError:
        # Contains non-ASCII characters - this is fine for translations
        pass
    
    # Check for null bytes or control characters
    if '\x00' in msgid or any(ord(c) < 32 and c not in '\t\n\r' for c in msgid):
        encoding_issues.append("Contains null bytes or invalid control characters")
    
    if encoding_issues:
        warnings.extend(encoding_issues)
    
    # 5. Length warnings for UI elements
    if msgstr:
        length_ratio = len(msgstr) / len(msgid) if len(msgid) > 0 else 1
        
        # Common UI element patterns that should stay roughly the same length
        ui_patterns = ['button', 'label', 'menu', 'tab', 'link']
        is_ui_element = any(pattern in msgid.lower() for pattern in ui_patterns)
        
        if is_ui_element and (length_ratio > 2.0 or length_ratio < 0.5):
            warnings.append(f"Translation length significantly different from source (ratio: {length_ratio:.2f})")
    
    # Return validation result
    is_valid = len([w for w in warnings if 'Missing critical' in w or 'unsafe content' in w]) == 0
    
    return is_valid, warnings


def validate_po_file_structure(content: str) -> Tuple[bool, List[str]]:
    """
    Advanced validation of PO file structure and content.
    
    Args:
        content: Complete PO file content
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    warnings = []
    
    # Check for required header
    if not content.startswith('#') and 'msgid ""' not in content[:500]:
        errors.append("Missing PO file header")
    
    # Parse entries and validate each
    entry_pattern = r'(?:^#.*\n)*?^msgid\s+"([^"]*(?:"[^"]*)*)".*?^msgstr\s+"([^"]*(?:"[^"]*)*)"'
    entries = re.findall(entry_pattern, content, re.MULTILINE | re.DOTALL)
    
    if not entries:
        errors.append("No valid msgid/msgstr pairs found")
    else:
        entry_count = 0
        valid_entries = 0
        
        for msgid, msgstr in entries:
            entry_count += 1
            
            # Validate individual entry
            is_valid, entry_warnings = validate_po_entry_content(msgid, msgstr)
            
            if is_valid:
                valid_entries += 1
            
            if entry_warnings:
                warnings.extend([f"Entry {entry_count}: {w}" for w in entry_warnings])
        
        # Summary validation
        if valid_entries == 0:
            errors.append("No valid entries found")
        elif valid_entries < entry_count * 0.8:  # If less than 80% are valid
            errors.append(f"Too many invalid entries: {entry_count - valid_entries}/{entry_count}")
    
    # Check for encoding declaration
    if 'Content-Type:' not in content or 'charset=' not in content:
        warnings.append("Missing or incomplete charset declaration")
    
    # Check for proper escaping
    if '\\n' in content and '\n' in content:
        warnings.append("Mixed line ending styles detected")
    
    is_valid = len(errors) == 0
    
    return is_valid, errors + warnings


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by removing/replacing dangerous characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    if not filename:
        return "unknown"
    
    # Remove path separators and other dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure it's not empty after sanitization
    if not sanitized:
        sanitized = "unknown"
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        sanitized = name[:255-len(ext)] + ext
    
    return sanitized


def validate_email(email: str) -> bool:
    """
    Basic email validation.
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not email:
        return False
    
    # Basic email regex pattern
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_url(url: str) -> bool:
    """
    Basic URL validation.
    
    Args:
        url: URL to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not url:
        return False
    
    # Basic URL pattern
    pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/.*)?$'
    return bool(re.match(pattern, url))


def normalize_language_code(language_code: str) -> str:
    """
    Normalize language code to standard format.
    
    Args:
        language_code: Language code to normalize
        
    Returns:
        Normalized language code
    """
    if not language_code:
        return language_code
    
    # Convert to lowercase and strip whitespace
    normalized = language_code.lower().strip()
    
    # Handle common variations
    language_mappings = {
        "en-us": "en",
        "en-gb": "en",
        "zh-cn": "zh-CN",  # Simplified Chinese
        "zh-tw": "zh-HK",  # Traditional Chinese (map Taiwan to Hong Kong)
        "zh-hk": "zh-HK",  # Hong Kong uses Traditional
        "zh": "zh-CN",     # Default Chinese to Simplified
        "pt-br": "pt",
        "pt-pt": "pt",
        "es-es": "es",
        "es-mx": "es",
        "fr-fr": "fr",
        "fr-ca": "fr"
    }
    
    return language_mappings.get(normalized, normalized)


def validate_batch_size(batch_size: int, min_size: int = 1, max_size: int = 100) -> int:
    """
    Validate and normalize batch size.
    
    Args:
        batch_size: Batch size to validate
        min_size: Minimum allowed size
        max_size: Maximum allowed size
        
    Returns:
        Validated batch size
    """
    if batch_size < min_size:
        return min_size
    elif batch_size > max_size:
        return max_size
    else:
        return batch_size 