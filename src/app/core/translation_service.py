"""
Translation service for the Translation Tool.
Orchestrates translation workflows using DeepSeek API and PO file processing.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

import polib
from loguru import logger

from ..config import settings
from ..models.translation_models import (
    TranslationJob, 
    TranslationStatus, 
    TranslationProgress,
    TranslationBatch
)
from ..models.po_models import POFile, POEntry
from .deepseek_client import get_deepseek_client
from .file_manager import get_file_manager
from .po_parser import POFileParser
from ..utils.exceptions import (
    TranslationServiceError, 
    JobNotFoundError, 
    LanguageNotSupportedError,
    JobProcessingError
)


class TranslationService:
    """
    Core translation service that orchestrates the translation workflow.
    Manages jobs, coordinates between components, and tracks progress.
    """
    
    def __init__(self):
        self.jobs: Dict[str, TranslationJob] = {}
        self.file_manager = get_file_manager()
        self.po_parser = POFileParser()
        
        # Dynamic batch sizing based on content
        self.base_batch_size = settings.batch_size
        self.max_batch_size = 50  # Maximum batch size
        self.min_batch_size = 5   # Minimum batch size
        
        # Progress tracking
        self.progress_callbacks: Dict[str, List[Callable[[str, int, str], None]]] = {}
        self.active_jobs: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.concurrent_translations = settings.translation_config.concurrent_translations
        self.job_timeout = settings.translation_config.job_timeout
    
    async def create_translation_job(
        self,
        file_info: Dict[str, Any],
        target_language: str,
        source_language: str = "auto"
    ) -> TranslationJob:
        """
        Create a new translation job.
        
        Args:
            file_info: File information from file upload
            target_language: Target language code
            source_language: Source language code
            
        Returns:
            TranslationJob instance
        """
        try:
            # Validate target language
            await self._validate_language(target_language)
            
            # Create job
            job_id = file_info.get("job_id") or str(uuid.uuid4())
            
            job = TranslationJob(
                job_id=job_id,
                filename=file_info["original_filename"],
                source_language=source_language,
                target_language=target_language,
                status=TranslationStatus.PENDING,
                created_at=datetime.utcnow(),
                file_path=file_info["file_path"],
                file_size=file_info["file_size"]
            )
            
            # Store job
            self.jobs[job_id] = job
            
            logger.info(f"Created translation job {job_id}: {job.filename} -> {target_language}")
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to create translation job: {e}")
            raise TranslationServiceError(f"Failed to create translation job: {str(e)}")
    
    async def start_translation(self, job_id: str) -> None:
        """
        Start translation process for a job.
        
        Args:
            job_id: Translation job ID
        """
        job = self.get_job(job_id)
        
        if job.status != TranslationStatus.PENDING:
            raise JobProcessingError(f"Job {job_id} is not in pending status")
        
        try:
            # Update job status
            job.status = TranslationStatus.PROCESSING
            job.started_at = datetime.utcnow()
            await self._notify_progress(job_id, 0, "Starting translation...", 0)
            
            # Start translation in background
            asyncio.create_task(self._process_translation_job(job))
            
            logger.info(f"Started translation job {job_id}")
            
        except Exception as e:
            job.status = TranslationStatus.FAILED
            job.error_message = str(e)
            logger.error(f"Failed to start translation job {job_id}: {e}")
            raise TranslationServiceError(f"Failed to start translation: {str(e)}")
    
    async def _process_translation_job(self, job: TranslationJob) -> None:
        """Process a translation job asynchronously."""
        try:
            await self._notify_progress(job.job_id, 5, "Parsing PO file...", 0)
            
            # Parse PO file
            po_file = await self._parse_po_file(job.file_path)
            
            # Filter entries that need translation
            translatable_entries = [
                entry for entry in po_file.entries 
                if entry.msgid and (
                    # For entries with plural forms, check if ANY plural translation is missing
                    (entry.msgid_plural and not any(val.strip() for val in entry.msgstr_plural.values())) or
                    # For non-plural entries, check if msgstr is missing
                    (not entry.msgid_plural and not entry.msgstr.strip())
                )
            ]
            
            total_entries = len(translatable_entries)
            
            if total_entries == 0:
                await self._notify_progress(job.job_id, 100, "No translations needed.", 0)
                await self._complete_job_with_no_translations(job, po_file)
                return
            
            # Initialize progress tracking
            if job.progress is None:
                job.progress = TranslationProgress(job_id=job.job_id)
            job.progress.total_entries = total_entries
            job.progress.processed_entries = 0
            job.progress.successful_translations = 0
            
            await self._notify_progress(
                job.job_id, 
                10, 
                f"Found {total_entries} entries to translate...",
                0
            )
            
            # Calculate dynamic batch size based on content complexity
            optimal_batch_size = self._calculate_optimal_batch_size(translatable_entries)
            logger.info(f"Using batch size {optimal_batch_size} for job {job.job_id}")
            
            translated_count = 0
            
            # Process in batches with rate limiting awareness
            batch_delay = self._calculate_batch_delay(total_entries)
            
            for i in range(0, total_entries, optimal_batch_size):
                batch = translatable_entries[i:i + optimal_batch_size]
                
                # Extract texts and contexts
                texts = [entry.msgid for entry in batch]
                contexts = [entry.msgctxt for entry in batch]
                
                # Translate batch with enhanced retry logic
                try:
                    deepseek_client = await get_deepseek_client()
                    async with deepseek_client:
                        translated_texts = await deepseek_client.translate_batch(
                            texts=texts,
                            target_language=job.target_language,
                            source_language=job.source_language,
                            contexts=contexts
                        )
                    
                    # Update entries with translations
                    for j, translated_text in enumerate(translated_texts):
                        if translated_text and translated_text.strip() and translated_text != texts[j]:
                            # Clean up the translated text (remove extra quotes)
                            cleaned_text = self._clean_translation_text(translated_text)
                            
                            # Only count as translated if it's different from original
                            entry = batch[j]
                            
                            if entry.msgid_plural:
                                # For plural entries, set plural translations
                                entry.msgstr_plural = {0: cleaned_text}
                                # Could also translate the plural form separately
                                # but for now, use the same translation for all plural forms
                                entry.msgstr = ""  # Clear single msgstr for plural entries
                            else:
                                # For single entries, set regular msgstr
                                entry.msgstr = cleaned_text
                            
                            translated_count += 1
                        elif translated_text == texts[j]:
                            # This means translation failed and original was returned
                            logger.warning(f"Translation failed for entry: {texts[j][:50]}...")
                            # Keep original msgstr empty for failed translations
                    
                    # Update progress
                    progress = 20 + int((i + len(batch)) / total_entries * 60)
                    await self._notify_progress(
                        job.job_id, 
                        progress, 
                        f"Translated {translated_count}/{total_entries} entries... (Batch {i//optimal_batch_size + 1})",
                        translated_count
                    )
                    
                    # Apply inter-batch delay to respect rate limits
                    if i + optimal_batch_size < total_entries and batch_delay > 0:
                        await asyncio.sleep(batch_delay)
                    
                except Exception as e:
                    logger.error(f"Batch translation failed for job {job.job_id}: {e}")
                    # Continue with next batch, don't fail entire job
                    await self._notify_progress(
                        job.job_id, 
                        20 + int((i + len(batch)) / total_entries * 60), 
                        f"Batch failed, continuing... ({str(e)[:50]})",
                        translated_count
                    )
                    continue
            
            # Update PO file metadata (preserve original, only update necessary fields)
            po_file.metadata.language = job.target_language
            po_file.metadata.last_translator = "DeepSeek Translation Tool v2.0"
            po_file.metadata.po_revision_date = datetime.utcnow()
            # Keep original metadata for other fields
            
            # Save translated PO file
            await self._notify_progress(job.job_id, 90, "Saving translated file...", translated_count)
            
            translated_content = self._po_file_to_string(po_file)
            
            processed_file_info = await self.file_manager.create_processed_file(
                job_id=job.job_id,
                content=translated_content,
                filename=job.filename,
                target_language=job.target_language
            )
            
            # Prepare download file
            download_info = await self.file_manager.prepare_download_file(
                job_id=job.job_id,
                processed_file_info=processed_file_info
            )
            
            # Complete job
            job.status = TranslationStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
            # Update progress object
            job.progress.processed_entries = translated_count
            job.progress.successful_translations = translated_count
            job.progress.completed_at = job.completed_at
            
            # Set output file information
            job.output_file_path = processed_file_info["file_path"]
            job.download_url = f"/api/v1/download/{job.job_id}"
            
            await self._notify_progress(
                job.job_id, 
                100, 
                f"Translation completed! {translated_count}/{total_entries} entries translated.",
                translated_count
            )
            
            logger.info(f"Translation job {job.job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Translation job {job.job_id} failed: {e}")
            job.status = TranslationStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            
            # Get current progress percentage
            current_progress = 0
            if job.progress and job.progress.total_entries > 0:
                current_progress = int((job.progress.processed_entries / job.progress.total_entries) * 100)
            
            await self._notify_progress(
                job.job_id, 
                current_progress, 
                f"Translation failed: {str(e)}",
                job.progress.processed_entries if job.progress else 0
            )
    
    def _calculate_optimal_batch_size(self, entries: List) -> int:
        """Calculate optimal batch size based on content complexity."""
        if not entries:
            return self.base_batch_size
        
        # Sample first 100 entries to analyze complexity
        sample_size = min(100, len(entries))
        sample_entries = entries[:sample_size]
        
        # Calculate average text length
        total_length = sum(len(entry.msgid) for entry in sample_entries)
        avg_length = total_length / sample_size
        
        # Count complex entries (HTML, variables, long text)
        complex_count = 0
        for entry in sample_entries:
            text = entry.msgid
            if (
                len(text) > 200 or  # Long text
                '<' in text or     # HTML tags
                '%' in text or     # Printf variables
                '{' in text or     # Template variables
                '\\n' in text      # Newlines
            ):
                complex_count += 1
        
        complexity_ratio = complex_count / sample_size
        
        # Adjust batch size based on complexity
        if complexity_ratio > 0.5 or avg_length > 150:
            # High complexity: smaller batches
            return max(self.min_batch_size, self.base_batch_size // 2)
        elif complexity_ratio < 0.2 and avg_length < 50:
            # Low complexity: larger batches
            return min(self.max_batch_size, self.base_batch_size * 2)
        else:
            # Medium complexity: standard batch size
            return self.base_batch_size
    
    def _calculate_batch_delay(self, total_entries: int) -> float:
        """Calculate delay between batches to respect rate limits."""
        # For large files, add delay to avoid rate limiting
        if total_entries > 1000:
            return 2.0  # 2 seconds between batches
        elif total_entries > 500:
            return 1.0  # 1 second between batches
        else:
            return 0.5  # 0.5 seconds for smaller files
    
    def _clean_translation_text(self, text: str) -> str:
        """Clean up translated text by removing unnecessary quotes and formatting."""
        if not text:
            return text
            
        cleaned = text.strip()
        
        # Remove extra quotes that might be added by the AI
        # Only remove if the entire string is wrapped in quotes
        if (cleaned.startswith('"') and cleaned.endswith('"') and 
            cleaned.count('"') == 2):
            cleaned = cleaned[1:-1]
        elif (cleaned.startswith("'") and cleaned.endswith("'") and 
              cleaned.count("'") == 2):
            cleaned = cleaned[1:-1]
        
        # Handle escaped quotes within the text
        cleaned = cleaned.replace('\\"', '"').replace("\\'", "'")
        
        return cleaned
    

    
    async def _parse_po_file(self, file_path: str) -> POFile:
        """Parse PO file and return POFile object."""
        try:
            return await self.po_parser.parse_file(file_path)
            
        except Exception as e:
            raise TranslationServiceError(f"Failed to parse PO file: {str(e)}")
    
    def _po_file_to_string(self, po_file: POFile) -> str:
        """Convert POFile back to string format."""
        try:
            # Create polib.POFile object
            po = polib.POFile()
            
            # Set metadata from POFileMetadata model
            metadata_dict = {}
            if po_file.metadata.project_id_version:
                metadata_dict["Project-Id-Version"] = po_file.metadata.project_id_version
            if po_file.metadata.pot_creation_date:
                metadata_dict["POT-Creation-Date"] = po_file.metadata.pot_creation_date.strftime("%Y-%m-%d %H:%M%z")
            if po_file.metadata.po_revision_date:
                metadata_dict["PO-Revision-Date"] = po_file.metadata.po_revision_date.strftime("%Y-%m-%d %H:%M%z")
            if po_file.metadata.last_translator:
                metadata_dict["Last-Translator"] = po_file.metadata.last_translator
            if po_file.metadata.language_team:
                metadata_dict["Language-Team"] = po_file.metadata.language_team
            if po_file.metadata.language:
                metadata_dict["Language"] = po_file.metadata.language
            if po_file.metadata.mime_version:
                metadata_dict["MIME-Version"] = po_file.metadata.mime_version
            if po_file.metadata.content_type:
                metadata_dict["Content-Type"] = po_file.metadata.content_type
            if po_file.metadata.content_transfer_encoding:
                metadata_dict["Content-Transfer-Encoding"] = po_file.metadata.content_transfer_encoding
            if po_file.metadata.plural_forms:
                metadata_dict["Plural-Forms"] = po_file.metadata.plural_forms
            
            po.metadata = metadata_dict
            
            # Add entries
            for entry in po_file.entries:
                po_entry = polib.POEntry(
                    msgid=entry.msgid,
                    msgstr=entry.msgstr,
                    msgctxt=entry.msgctxt,
                    msgid_plural=entry.msgid_plural if entry.msgid_plural else None,
                    msgstr_plural=entry.msgstr_plural if entry.msgstr_plural else {},
                    comment="\n".join(entry.comments) if entry.comments else "",
                    tcomment="\n".join(entry.auto_comments) if entry.auto_comments else "",
                    occurrences=[(ref.split(':')[0], ref.split(':')[1] if ':' in ref else "") for ref in entry.occurrences],
                    flags=entry.flags if entry.flags else []
                )
                po.append(po_entry)
            
            return str(po)
            
        except Exception as e:
            raise TranslationServiceError(f"Failed to convert PO file to string: {str(e)}")
    
    async def _complete_job_with_no_translations(self, job: TranslationJob, po_file: POFile) -> None:
        """Complete job when no translations are needed."""
        try:
            # Save original file as processed (no changes needed)
            original_content = self._po_file_to_string(po_file)
            
            processed_file_info = await self.file_manager.create_processed_file(
                job_id=job.job_id,
                content=original_content,
                filename=job.filename,
                target_language=job.target_language
            )
            
            download_info = await self.file_manager.prepare_download_file(
                job_id=job.job_id,
                processed_file_info=processed_file_info
            )
            
            # Complete job
            job.status = TranslationStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            
            # Update progress object
            if job.progress is None:
                job.progress = TranslationProgress(job_id=job.job_id)
            job.progress.total_entries = 0
            job.progress.processed_entries = 0
            job.progress.successful_translations = 0
            job.progress.completed_at = job.completed_at
            
            # Set output file information
            job.output_file_path = processed_file_info["file_path"]
            job.download_url = f"/api/v1/download/{job.job_id}"
            
            await self._notify_progress(
                job.job_id, 
                100, 
                "No translations needed - file already complete.",
                0
            )
            
            logger.info(f"Translation job {job.job_id} completed with no translations needed")
            
        except Exception as e:
            job.status = TranslationStatus.FAILED
            job.error_message = str(e)
            raise
    
    async def _validate_language(self, language_code: str) -> None:
        """Validate language code is supported."""
        try:
            deepseek_client = await get_deepseek_client()
            async with deepseek_client:
                supported_languages = await deepseek_client.get_supported_languages()
                
            supported_codes = [lang["code"] for lang in supported_languages]
            
            if language_code not in supported_codes:
                raise LanguageNotSupportedError(
                    f"Language '{language_code}' is not supported. "
                    f"Supported languages: {', '.join(supported_codes)}"
                )
                
        except LanguageNotSupportedError:
            raise
        except Exception as e:
            logger.warning(f"Could not validate language {language_code}: {e}")
            # Don't fail validation if we can't check - allow the translation to proceed
    
    def get_job(self, job_id: str) -> TranslationJob:
        """Get translation job by ID."""
        if job_id not in self.jobs:
            raise JobNotFoundError(f"Translation job {job_id} not found")
        
        return self.jobs[job_id]
    
    def get_all_jobs(self) -> List[TranslationJob]:
        """Get all translation jobs."""
        return list(self.jobs.values())
    
    def get_jobs_by_status(self, status: TranslationStatus) -> List[TranslationJob]:
        """Get jobs by status."""
        return [job for job in self.jobs.values() if job.status == status]
    
    async def cancel_job(self, job_id: str) -> None:
        """Cancel a translation job."""
        job = self.get_job(job_id)
        
        if job.status in [TranslationStatus.COMPLETED, TranslationStatus.FAILED]:
            raise JobProcessingError(f"Cannot cancel job {job_id} in status {job.status}")
        
        job.status = TranslationStatus.FAILED
        job.error_message = "Job cancelled by user"
        job.completed_at = datetime.utcnow()
        
        # Get current progress percentage
        current_progress = 0
        if job.progress and job.progress.total_entries > 0:
            current_progress = int((job.progress.processed_entries / job.progress.total_entries) * 100)
        
        await self._notify_progress(job_id, current_progress, "Job cancelled", job.progress.processed_entries if job.progress else 0)
        
        logger.info(f"Translation job {job_id} cancelled")
    
    async def retry_job(self, job_id: str) -> None:
        """Retry a failed translation job."""
        job = self.get_job(job_id)
        
        if job.status != TranslationStatus.FAILED:
            raise JobProcessingError(f"Can only retry failed jobs, job {job_id} is {job.status}")
        
        # Reset job status
        job.status = TranslationStatus.PENDING
        job.error_message = None
        
        # Reset progress object
        if job.progress is None:
            job.progress = TranslationProgress(job_id=job.job_id)
        job.progress.processed_entries = 0
        job.progress.successful_translations = 0
        job.progress.failed_translations = 0
        job.progress.current_error = None
        job.progress.started_at = None
        job.progress.completed_at = None
        
        job.started_at = None
        job.completed_at = None
        
        # Start translation
        await self.start_translation(job_id)
    
    def subscribe_to_progress(self, job_id: str, callback: Callable[[str, int, str], None]) -> None:
        """Subscribe to job progress updates."""
        if job_id not in self.progress_callbacks:
            self.progress_callbacks[job_id] = []
        
        self.progress_callbacks[job_id].append(callback)
    
    def unsubscribe_from_progress(self, job_id: str, callback: Callable[[str, int, str], None]) -> None:
        """Unsubscribe from job progress updates."""
        if job_id in self.progress_callbacks:
            try:
                self.progress_callbacks[job_id].remove(callback)
            except ValueError:
                pass
    
    async def _notify_progress(self, job_id: str, progress_percentage: int, message: str, processed_entries: int = None) -> None:
        """Notify progress callbacks and update job progress."""
        # Update job progress
        if job_id in self.jobs:
            job = self.jobs[job_id]
            if job.progress is None:
                job.progress = TranslationProgress(job_id=job_id)
            
            # Update processed entries if provided
            if processed_entries is not None:
                job.progress.processed_entries = processed_entries
            
            # Store current message in progress
            job.progress.current_error = message if "error" in message.lower() or "fail" in message.lower() else None
        
        # Notify callbacks
        if job_id in self.progress_callbacks:
            for callback in self.progress_callbacks[job_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(job_id, progress_percentage, message)
                    else:
                        callback(job_id, progress_percentage, message)
                except Exception as e:
                    logger.error(f"Progress callback error for job {job_id}: {e}")
    
    async def cleanup_completed_jobs(self, older_than_hours: int = 24) -> None:
        """Clean up old completed jobs."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
            
            jobs_to_cleanup = []
            for job_id, job in self.jobs.items():
                if (job.status in [TranslationStatus.COMPLETED, TranslationStatus.FAILED] and
                    job.completed_at and job.completed_at < cutoff_time):
                    jobs_to_cleanup.append(job_id)
            
            for job_id in jobs_to_cleanup:
                # Clean up files
                await self.file_manager.cleanup_job_files(job_id)
                
                # Remove from memory
                del self.jobs[job_id]
                
                # Clean up progress callbacks
                if job_id in self.progress_callbacks:
                    del self.progress_callbacks[job_id]
                
                logger.info(f"Cleaned up completed job {job_id}")
            
            if jobs_to_cleanup:
                logger.info(f"Cleaned up {len(jobs_to_cleanup)} completed jobs")
                
        except Exception as e:
            logger.error(f"Failed to cleanup completed jobs: {e}")


# Global translation service instance
_translation_service: Optional[TranslationService] = None


def get_translation_service() -> TranslationService:
    """Get or create translation service instance."""
    global _translation_service
    
    if _translation_service is None:
        _translation_service = TranslationService()
    
    return _translation_service


async def start_cleanup_task():
    """Start background task for job cleanup."""
    translation_service = get_translation_service()
    
    while True:
        try:
            await asyncio.sleep(3600)  # Run every hour
            await translation_service.cleanup_completed_jobs()
        except Exception as e:
            logger.error(f"Job cleanup task error: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes before retrying 