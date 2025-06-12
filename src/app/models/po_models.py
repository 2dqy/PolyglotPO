"""
Pydantic models for PO file data structures.
Represents PO entries, files, and metadata.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator


class POEntry(BaseModel):
    """Represents a single PO file entry (msgid/msgstr pair)."""
    
    msgid: str = Field(..., description="Original message ID")
    msgstr: str = Field(default="", description="Translated message string") 
    msgctxt: Optional[str] = Field(None, description="Message context")
    msgid_plural: Optional[str] = Field(None, description="Plural form of msgid")
    msgstr_plural: Dict[int, str] = Field(default_factory=dict, description="Plural translations")
    
    # Format preservation fields (new)
    original_msgid_format: Optional[str] = Field(None, description="Original msgid with exact formatting")
    original_msgstr_format: Optional[str] = Field(None, description="Original msgstr with exact formatting")
    original_msgctxt_format: Optional[str] = Field(None, description="Original msgctxt with exact formatting")
    
    # Additional metadata
    occurrences: List[str] = Field(default_factory=list, description="Source file occurrences")
    flags: List[str] = Field(default_factory=list, description="Entry flags")
    comments: List[str] = Field(default_factory=list, description="Translator comments")
    auto_comments: List[str] = Field(default_factory=list, description="Automatic comments")
    
    # Processing metadata
    is_translated: bool = Field(default=False, description="Whether entry is translated")
    is_fuzzy: bool = Field(default=False, description="Whether entry is fuzzy")
    is_obsolete: bool = Field(default=False, description="Whether entry is obsolete")
    
    @validator('msgid')
    def msgid_not_empty_unless_header(cls, v):
        """Validate msgid - can only be empty for header entry."""
        return v
    
    @validator('is_translated', always=True)
    def set_is_translated(cls, v, values):
        """Automatically determine if entry is translated."""
        msgstr = values.get('msgstr', '')
        msgstr_plural = values.get('msgstr_plural', {})
        
        if msgstr.strip():
            return True
        if msgstr_plural and any(val.strip() for val in msgstr_plural.values()):
            return True
        return False
    
    @validator('is_fuzzy', always=True) 
    def set_is_fuzzy(cls, v, values):
        """Check if entry is marked as fuzzy."""
        flags = values.get('flags', [])
        return 'fuzzy' in flags
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return self.dict()
    
    def get_display_text(self, max_length: int = 100) -> str:
        """Get truncated display text for UI."""
        text = self.msgid
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text


class POFileMetadata(BaseModel):
    """Metadata from PO file header."""
    
    project_id_version: Optional[str] = Field(None, description="Project ID and version")
    pot_creation_date: Optional[datetime] = Field(None, description="POT creation date")
    po_revision_date: Optional[datetime] = Field(None, description="PO revision date")
    last_translator: Optional[str] = Field(None, description="Last translator info")
    language_team: Optional[str] = Field(None, description="Language team info")
    language: Optional[str] = Field(None, description="Language code")
    mime_version: Optional[str] = Field(None, description="MIME version")
    content_type: str = Field(default="text/plain; charset=utf-8", description="Content type")
    content_transfer_encoding: str = Field(default="8bit", description="Transfer encoding")
    plural_forms: Optional[str] = Field(None, description="Plural forms definition")
    
    # Additional metadata
    charset: str = Field(default="utf-8", description="Character encoding")
    
    @validator('pot_creation_date', 'po_revision_date', pre=True)
    def parse_datetime(cls, v):
        """Parse datetime from PO file format."""
        if isinstance(v, str):
            try:
                # Try parsing common PO date format: "YYYY-MM-DD HH:MM+ZZZZ"
                return datetime.fromisoformat(v.replace('+0800', '+08:00'))
            except:
                # If parsing fails, return None
                return None
        return v


class POFile(BaseModel):
    """Represents a complete PO file with entries and metadata."""
    
    # File identification
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    
    # Metadata
    metadata: POFileMetadata = Field(default_factory=POFileMetadata, description="File metadata")
    
    # Entries
    entries: List[POEntry] = Field(default_factory=list, description="PO file entries")
    
    # Statistics
    total_entries: int = Field(default=0, description="Total number of entries")
    translated_entries: int = Field(default=0, description="Number of translated entries")
    fuzzy_entries: int = Field(default=0, description="Number of fuzzy entries")
    untranslated_entries: int = Field(default=0, description="Number of untranslated entries")
    
    # Processing info
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    source_language: str = Field(default="en", description="Source language code")
    
    @validator('total_entries', always=True)
    def calculate_total_entries(cls, v, values):
        """Calculate total entries."""
        entries = values.get('entries', [])
        return len(entries)
    
    @validator('translated_entries', always=True)
    def calculate_translated_entries(cls, v, values):
        """Calculate translated entries."""
        entries = values.get('entries', [])
        return len([e for e in entries if e.is_translated])
    
    @validator('fuzzy_entries', always=True)
    def calculate_fuzzy_entries(cls, v, values):
        """Calculate fuzzy entries."""
        entries = values.get('entries', [])
        return len([e for e in entries if e.is_fuzzy])
    
    @validator('untranslated_entries', always=True) 
    def calculate_untranslated_entries(cls, v, values):
        """Calculate untranslated entries."""
        entries = values.get('entries', [])
        return len([e for e in entries if not e.is_translated])
    
    def get_translation_progress(self) -> float:
        """Calculate translation progress percentage."""
        if self.total_entries == 0:
            return 0.0
        return (self.translated_entries / self.total_entries) * 100
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get file statistics summary."""
        return {
            "filename": self.filename,
            "file_size": self.file_size,
            "total_entries": self.total_entries,
            "translated_entries": self.translated_entries,
            "fuzzy_entries": self.fuzzy_entries,
            "untranslated_entries": self.untranslated_entries,
            "translation_progress": self.get_translation_progress(),
            "source_language": self.source_language,
            "target_language": self.metadata.language,
            "created_at": self.created_at
        }
    
    def get_entries_by_status(self, status: str) -> List[POEntry]:
        """Get entries filtered by translation status."""
        if status == "translated":
            return [e for e in self.entries if e.is_translated]
        elif status == "untranslated":
            return [e for e in self.entries if not e.is_translated]
        elif status == "fuzzy":
            return [e for e in self.entries if e.is_fuzzy]
        else:
            return self.entries 