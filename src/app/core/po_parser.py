"""
PO File Parser for handling Portable Object files.
Uses polib library for parsing and validation.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime

import polib
from loguru import logger

from ..models.po_models import POEntry, POFile, POFileMetadata
from ..config import settings


class POFileParser:
    """Parser for PO (Portable Object) files."""
    
    def __init__(self):
        """Initialize the PO file parser."""
        self.logger = logger.bind(component="POFileParser")
    
    async def parse_file(self, file_path: str) -> POFile:
        """
        Parse a PO file and return structured data.
        
        Args:
            file_path: Path to the PO file
            
        Returns:
            POFile: Parsed PO file data
            
        Raises:
            ValueError: If file is invalid or cannot be parsed
            FileNotFoundError: If file doesn't exist
        """
        try:
            file_path_obj = Path(file_path)
            
            if not file_path_obj.exists():
                raise FileNotFoundError(f"PO file not found: {file_path}")
            
            # Get file size
            file_size = file_path_obj.stat().st_size
            filename = file_path_obj.name
            
            self.logger.info(f"Parsing PO file: {filename} ({file_size} bytes)")
            
            # Read raw file content for format preservation
            with open(file_path, 'r', encoding='utf-8') as f:
                self.raw_content = f.read()
            
            # Parse with polib
            try:
                po_data = polib.pofile(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                # Try with different encodings
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        po_data = polib.pofile(file_path, encoding=encoding)
                        self.logger.warning(f"Successfully parsed with {encoding} encoding")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ValueError("Unable to decode PO file with any supported encoding")
            
            # Extract metadata
            metadata = self._extract_metadata(po_data)
            
            # Extract entries with format preservation
            entries = self._extract_entries(po_data)
            
            # Create POFile object
            po_file = POFile(
                filename=filename,
                file_size=file_size,
                metadata=metadata,
                entries=entries
            )
            
            self.logger.info(
                f"Successfully parsed PO file: {po_file.total_entries} entries, "
                f"{po_file.translated_entries} translated, "
                f"{po_file.untranslated_entries} untranslated"
            )
            
            return po_file
            
        except Exception as e:
            self.logger.error(f"Error parsing PO file {file_path}: {str(e)}")
            raise ValueError(f"Failed to parse PO file: {str(e)}")
    
    def _extract_metadata(self, po_data: polib.POFile) -> POFileMetadata:
        """Extract metadata from polib POFile object."""
        
        metadata = POFileMetadata()
        
        # Extract header information
        if hasattr(po_data, 'metadata') and po_data.metadata:
            for key, value in po_data.metadata.items():
                if key == "Project-Id-Version":
                    metadata.project_id_version = value
                elif key == "POT-Creation-Date":
                    metadata.pot_creation_date = self._parse_po_datetime(value)
                elif key == "PO-Revision-Date":
                    metadata.po_revision_date = self._parse_po_datetime(value)
                elif key == "Last-Translator":
                    metadata.last_translator = value
                elif key == "Language-Team":
                    metadata.language_team = value
                elif key == "Language":
                    metadata.language = value
                elif key == "MIME-Version":
                    metadata.mime_version = value
                elif key == "Content-Type":
                    metadata.content_type = value
                    # Extract charset from Content-Type
                    if "charset=" in value:
                        charset = value.split("charset=")[1].strip()
                        metadata.charset = charset
                elif key == "Content-Transfer-Encoding":
                    metadata.content_transfer_encoding = value
                elif key == "Plural-Forms":
                    metadata.plural_forms = value
        
        return metadata
    
    def _extract_entries(self, po_data: polib.POFile) -> List[POEntry]:
        """Extract entries from polib POFile object."""
        
        entries = []
        
        for entry in po_data:
            # Skip header entry (empty msgid)
            if not entry.msgid:
                continue
            
            # Create POEntry
            po_entry = POEntry(
                msgid=entry.msgid,
                msgstr=entry.msgstr,
                msgctxt=entry.msgctxt if entry.msgctxt else None,
                msgid_plural=entry.msgid_plural if entry.msgid_plural else None,
                msgstr_plural=dict(entry.msgstr_plural) if entry.msgstr_plural else {},
                # Store original format for preservation
                original_msgid_format=self._get_original_string_format(entry.msgid),
                original_msgstr_format=self._get_original_string_format(entry.msgstr) if entry.msgstr else None,
                original_msgctxt_format=self._get_original_string_format(entry.msgctxt) if entry.msgctxt else None,
                occurrences=[f"{occ[0]}:{occ[1]}" for occ in entry.occurrences],
                flags=list(entry.flags),
                comments=entry.tcomment.split('\n') if entry.tcomment else [],
                auto_comments=entry.comment.split('\n') if entry.comment else [],
                is_obsolete=entry.obsolete
            )
            
            entries.append(po_entry)
        
        return entries
    
    def _get_original_string_format(self, text: str) -> str:
        """
        Preserve the original string format for PO file strings.
        This method tries to extract the exact original format from the raw file content.
        """
        if not text or not hasattr(self, 'raw_content'):
            return self._format_po_string(text)
        
        # Try to find the exact original format in the raw content
        # This is a simple approach - for complex cases, you might need more sophisticated parsing
        
        # Escape special regex characters in the text
        import re
        escaped_text = re.escape(text)
        
        # Look for msgid pattern with this exact text
        patterns = [
            rf'msgid\s+("(?:[^"\\]|\\.)*"(?:\s*"(?:[^"\\]|\\.)*")*)',  # Single or multiline format
            rf'msgid\s+""[\s\n]*("(?:[^"\\]|\\.)*"(?:\s*"(?:[^"\\]|\\.)*")*)',  # Multiline starting with empty string
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, self.raw_content, re.MULTILINE | re.DOTALL)
            for match in matches:
                original_format = match.group(1)
                # Verify this is the right match by checking if it decodes to our text
                try:
                    if self._decode_po_string(original_format) == text:
                        return original_format
                except:
                    continue
        
        # Fallback to formatted version
        return self._format_po_string(text)

    def _decode_po_string(self, po_string: str) -> str:
        """Decode a PO format string back to plain text."""
        # Remove outer quotes and concatenate multiple quoted strings
        import re
        
        # Find all quoted strings
        quoted_strings = re.findall(r'"((?:[^"\\]|\\.)*)"', po_string)
        
        # Join them and decode escape sequences
        combined = ''.join(quoted_strings)
        
        # Decode common escape sequences
        decoded = combined.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
        
        return decoded

    def _format_po_string(self, text: str) -> str:
        """
        Format a string for PO file output (fallback method).
        """
        if not text:
            return '""'
        
        # Check if text contains newlines or is very long
        if '\n' in text or len(text) > 60:
            # Use multiline format
            lines = text.split('\n')
            if len(lines) > 1:
                # Multi-line string format
                formatted_lines = ['""']
                for line in lines[:-1]:  # All lines except last
                    escaped_line = line.replace('\\', '\\\\').replace('"', '\\"')
                    formatted_lines.append(f'"{escaped_line}\\n"')
                if lines[-1]:  # Last line if not empty
                    escaped_line = lines[-1].replace('\\', '\\\\').replace('"', '\\"')
                    formatted_lines.append(f'"{escaped_line}"')
                return '\n'.join(formatted_lines)
        
        # Single line format - escape quotes and backslashes
        escaped_text = text.replace('\\', '\\\\').replace('"', '\\"')
        return f'"{escaped_text}"'
    
    def _parse_po_datetime(self, date_str: str) -> Optional[datetime]:
        """Parse datetime from PO file format."""
        if not date_str:
            return None
        
        # Common PO date formats
        formats = [
            "%Y-%m-%d %H:%M%z",
            "%Y-%m-%d %H:%M:%S%z", 
            "%Y-%m-%d %H:%M+%Z",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        self.logger.warning(f"Could not parse datetime: {date_str}")
        return None
    
    async def validate_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """
        Validate a PO file structure and content.
        
        Args:
            file_path: Path to the PO file
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            file_path_obj = Path(file_path)
            
            # Check file exists
            if not file_path_obj.exists():
                errors.append("File does not exist")
                return False, errors
            
            # Check file size
            file_size = file_path_obj.stat().st_size
            if file_size == 0:
                errors.append("File is empty")
                return False, errors
            
            if file_size > settings.file_config.max_file_size:
                errors.append(f"File too large ({file_size} bytes). Maximum size is {settings.file_config.max_file_size} bytes")
                return False, errors
            
            # Check file extension
            if file_path_obj.suffix not in settings.file_config.allowed_extensions:
                errors.append(f"Invalid file extension. Allowed: {settings.file_config.allowed_extensions}")
                return False, errors
            
            # Try to parse with polib
            try:
                po_data = polib.pofile(file_path)
                
                # Check if file has any entries
                if len(po_data) == 0:
                    errors.append("PO file contains no entries")
                
                # Check for critical parsing issues
                if po_data.percent_translated() < 0:
                    errors.append("Invalid PO file structure")
                
            except Exception as e:
                errors.append(f"Invalid PO file format: {str(e)}")
                return False, errors
            
        except Exception as e:
            errors.append(f"File validation error: {str(e)}")
            return False, errors
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    async def write_po_file(self, po_file: POFile, output_path: str) -> bool:
        """
        Write POFile data back to a PO file with format preservation.
        
        Args:
            po_file: POFile object to write
            output_path: Path for output file
            
        Returns:
            bool: Success status
        """
        try:
            self.logger.info(f"Writing PO file with format preservation: {output_path}")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                # Write header
                self._write_po_header(f, po_file.metadata)
                
                # Write entries
                for entry in po_file.entries:
                    self._write_po_entry(f, entry)
            
            self.logger.info(f"Successfully wrote PO file: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing PO file {output_path}: {str(e)}")
            return False

    def _write_po_header(self, file_handle, metadata: POFileMetadata) -> None:
        """Write PO file header with metadata."""
        file_handle.write('# SOME DESCRIPTIVE TITLE.\n')
        file_handle.write('# Copyright (C) YEAR THE PACKAGE\'S COPYRIGHT HOLDER\n')
        file_handle.write('# This file is distributed under the same license as the PACKAGE package.\n')
        file_handle.write('# FIRST AUTHOR <EMAIL@ADDRESS>, YEAR.\n')
        file_handle.write('#\n')
        file_handle.write('msgid ""\n')
        file_handle.write('msgstr ""\n')
        
        # Write metadata
        if metadata.project_id_version:
            file_handle.write(f'"Project-Id-Version: {metadata.project_id_version}\\n"\n')
        if metadata.pot_creation_date:
            file_handle.write(f'"POT-Creation-Date: {metadata.pot_creation_date.strftime("%Y-%m-%d %H:%M%z")}\\n"\n')
        
        # Always update PO-Revision-Date to current time
        file_handle.write(f'"PO-Revision-Date: {datetime.utcnow().strftime("%Y-%m-%d %H:%M%z")}\\n"\n')
        
        if metadata.last_translator:
            file_handle.write(f'"Last-Translator: {metadata.last_translator}\\n"\n')
        if metadata.language_team:
            file_handle.write(f'"Language-Team: {metadata.language_team}\\n"\n')
        if metadata.language:
            file_handle.write(f'"Language: {metadata.language}\\n"\n')
        
        file_handle.write(f'"MIME-Version: {metadata.mime_version or "1.0"}\\n"\n')
        file_handle.write(f'"Content-Type: {metadata.content_type}\\n"\n')
        file_handle.write(f'"Content-Transfer-Encoding: {metadata.content_transfer_encoding}\\n"\n')
        
        if metadata.plural_forms:
            file_handle.write(f'"Plural-Forms: {metadata.plural_forms}\\n"\n')
        
        file_handle.write('\n')

    def _write_po_entry(self, file_handle, entry: POEntry) -> None:
        """Write a single PO entry with format preservation."""
        # Write translator comments
        if entry.comments:
            for comment in entry.comments:
                if comment.strip():
                    file_handle.write(f'# {comment}\n')
        
        # Write automatic comments  
        if entry.auto_comments:
            for comment in entry.auto_comments:
                if comment.strip():
                    file_handle.write(f'#. {comment}\n')
        
        # Write source references
        if entry.occurrences:
            file_handle.write(f'#: {" ".join(entry.occurrences)}\n')
        
        # Write flags
        if entry.flags:
            file_handle.write(f'#, {", ".join(entry.flags)}\n')
        
        # Write msgctxt if present
        if entry.msgctxt:
            if entry.original_msgctxt_format:
                file_handle.write(f'msgctxt {entry.original_msgctxt_format}\n')
            else:
                file_handle.write(f'msgctxt "{entry.msgctxt}"\n')
        
        # Write msgid with original format preservation
        if entry.original_msgid_format:
            file_handle.write(f'msgid {entry.original_msgid_format}\n')
        else:
            # Fallback to escaped format
            escaped_msgid = entry.msgid.replace('\\', '\\\\').replace('"', '\\"')
            file_handle.write(f'msgid "{escaped_msgid}"\n')
        
        # Write msgid_plural if present
        if entry.msgid_plural:
            escaped_plural = entry.msgid_plural.replace('\\', '\\\\').replace('"', '\\"')
            file_handle.write(f'msgid_plural "{escaped_plural}"\n')
        
        # Write msgstr or msgstr_plural
        if entry.msgstr_plural:
            # Write plural forms
            for idx, plural_str in entry.msgstr_plural.items():
                escaped_str = plural_str.replace('\\', '\\\\').replace('"', '\\"')
                file_handle.write(f'msgstr[{idx}] "{escaped_str}"\n')
        else:
            # Write single msgstr
            if entry.msgstr:
                if entry.original_msgstr_format:
                    file_handle.write(f'msgstr {entry.original_msgstr_format}\n')
                else:
                    escaped_str = entry.msgstr.replace('\\', '\\\\').replace('"', '\\"')
                    file_handle.write(f'msgstr "{escaped_str}"\n')
            else:
                file_handle.write('msgstr ""\n')
        
        file_handle.write('\n')
    
    def get_file_statistics(self, po_file: POFile) -> Dict[str, Any]:
        """Get comprehensive statistics for a PO file."""
        
        stats = po_file.get_statistics()
        
        # Add additional statistics
        entries_by_status = {
            'translated': len(po_file.get_entries_by_status('translated')),
            'untranslated': len(po_file.get_entries_by_status('untranslated')),
            'fuzzy': len(po_file.get_entries_by_status('fuzzy'))
        }
        
        # Analyze entry lengths
        entry_lengths = [len(entry.msgid) for entry in po_file.entries]
        if entry_lengths:
            stats.update({
                'average_entry_length': sum(entry_lengths) / len(entry_lengths),
                'max_entry_length': max(entry_lengths),
                'min_entry_length': min(entry_lengths)
            })
        
        # Count entries with context
        entries_with_context = len([e for e in po_file.entries if e.msgctxt])
        stats['entries_with_context'] = entries_with_context
        
        # Count plural entries
        plural_entries = len([e for e in po_file.entries if e.msgid_plural])
        stats['plural_entries'] = plural_entries
        
        stats['entries_by_status'] = entries_by_status
        
        return stats 