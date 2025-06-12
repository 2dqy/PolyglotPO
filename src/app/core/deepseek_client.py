"""
DeepSeek API client for translation services.
Handles API communication, rate limiting, and error recovery.
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import httpx
from loguru import logger

from ..config import settings
from ..utils.exceptions import TranslationAPIError, RateLimitError


class DeepSeekClient:
    """
    Async client for DeepSeek API integration.
    Handles authentication, rate limiting, and error recovery.
    """
    
    def __init__(self):
        """Initialize DeepSeek client with configuration."""
        self.api_key = settings.deepseek.api_key
        self.base_url = settings.deepseek.base_url
        self.model = "deepseek-chat"  # This points to DeepSeek-V3-0324 according to API docs
        self.max_tokens = settings.deepseek.max_tokens
        self.temperature = settings.deepseek.temperature
        self.timeout = settings.deepseek.timeout
        self.max_retries = settings.deepseek.max_retries
        self.retry_delay = settings.deepseek.retry_delay
        self.rate_limit = settings.deepseek.rate_limit
        
        # Rate limiting
        self.last_request_time = 0
        self.request_interval = 60.0 / self.rate_limit  # seconds between requests
        
        # HTTP client
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    async def _check_rate_limit(self) -> None:
        """Check and enforce rate limiting."""
        now = datetime.now()
        
        # Check if we're at the rate limit
        if (now - datetime.fromtimestamp(self.last_request_time)).total_seconds() < self.request_interval:
            sleep_time = self.request_interval - (now - datetime.fromtimestamp(self.last_request_time)).total_seconds()
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f} seconds")
                await asyncio.sleep(sleep_time)
        
        self.last_request_time = now.timestamp()
    
    async def _make_request(
        self, 
        endpoint: str, 
        payload: Dict[str, Any],
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        await self._check_rate_limit()
        client = await self._ensure_client()
        
        try:
            response = await client.post(
                f"{self.base_url}/{endpoint}",
                json=payload
            )
            
            if response.status_code == 429:  # Rate limited
                if retry_count < self.max_retries:
                    delay = self.retry_delay * (2 ** retry_count)  # Exponential backoff
                    logger.warning(f"Rate limited, retrying in {delay:.2f} seconds")
                    await asyncio.sleep(delay)
                    return await self._make_request(endpoint, payload, retry_count + 1)
                else:
                    raise RateLimitError("Rate limit exceeded, max retries reached")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.RequestError as e:
            error_msg = str(e) if str(e) else "Network connection error"
            if retry_count < self.max_retries:
                delay = self.retry_delay * (2 ** retry_count)
                logger.warning(f"Request failed: {error_msg}, retrying in {delay:.2f} seconds")
                await asyncio.sleep(delay)
                return await self._make_request(endpoint, payload, retry_count + 1)
            else:
                raise TranslationAPIError(f"Request failed after {self.max_retries} retries: {error_msg}")
        
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            logger.error(f"API request failed: {error_msg}")
            raise TranslationAPIError(error_msg)
    
    def _create_translation_prompt(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "auto",
        context: Optional[str] = None
    ) -> str:
        """Create professional localization prompt optimized for DeepSeek V3."""
        language_names = {
            "es": "Spanish", "fr": "French", "de": "German", "it": "Italian",
            "pt": "Portuguese", "ru": "Russian", "ja": "Japanese", "ko": "Korean",
            "zh-CN": "Simplified Chinese", "zh-HK": "Traditional Chinese (Hong Kong)", 
            "ar": "Arabic", "nl": "Dutch", "sv": "Swedish",
            "no": "Norwegian", "da": "Danish", "fi": "Finnish", "pl": "Polish",
            "cs": "Czech", "hu": "Hungarian", "ro": "Romanian", "bg": "Bulgarian"
        }
        
        target_lang_name = language_names.get(target_language, target_language)
        
        # Optimized prompt for DeepSeek V3's improved reasoning capabilities  
        prompt = f"""Translate the following text to {target_lang_name} for professional software interface localization.

CRITICAL REQUIREMENTS:
- Return ONLY the translated text, no quotes, explanations or notes
- Use formal, professional language appropriate for business software interfaces
- For Traditional Chinese (Hong Kong): use standard Traditional Chinese, NOT Cantonese colloquialisms
- Preserve ALL technical markers exactly: %s, %d, @variables, {{placeholders}}, HTML tags, URLs
- Keep proper nouns and brand names unchanged  
- Maintain original formatting and structure
- Do NOT add extra quotation marks around the translation
- If text is empty or only whitespace, return it unchanged

Text to translate: "{text}"

Translation:"""
        
        return prompt
    
    async def translate_text(
        self, 
        text: str, 
        target_language: str, 
        source_language: str = "auto",
        context: Optional[str] = None
    ) -> str:
        """
        Translate a single text string.
        
        Args:
            text: Text to translate
            target_language: Target language code (e.g., 'es', 'fr')
            source_language: Source language code (default: 'auto')
            context: Optional context for better translation
            
        Returns:
            Translated text
        """
        if not text or not text.strip():
            return text
        
        try:
            prompt = self._create_translation_prompt(text, target_language, source_language, context)
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature
            }
            
            response = await self._make_request("chat/completions", payload)
            
            translated_text = response["choices"][0]["message"]["content"].strip()
            
            logger.debug(f"Translated '{text[:50]}...' to '{translated_text[:50]}...'")
            
            return translated_text
            
        except Exception as e:
            logger.error(f"Translation failed for text '{text[:100]}...': {e}")
            raise TranslationAPIError(f"Translation failed: {str(e)}")
    
    async def translate_batch(
        self, 
        texts: List[str], 
        target_language: str, 
        source_language: str = "auto",
        contexts: Optional[List[str]] = None
    ) -> List[str]:
        """
        Translate multiple texts concurrently with smart retry logic.
        
        Args:
            texts: List of texts to translate
            target_language: Target language code
            source_language: Source language code
            contexts: Optional list of contexts for each text
            
        Returns:
            List of translated texts (original text returned for failed translations)
        """
        if not texts:
            return []
        
        # Prepare contexts
        if contexts is None:
            contexts = [None] * len(texts)
        
        # Create translation tasks
        tasks = []
        for i, text in enumerate(texts):
            context = contexts[i] if i < len(contexts) else None
            task = self.translate_text(text, target_language, source_language, context)
            tasks.append(task)
        
        # Execute translations concurrently with semaphore
        semaphore = asyncio.Semaphore(settings.translation_config.concurrent_translations)
        
        async def translate_with_semaphore(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[translate_with_semaphore(task) for task in tasks],
            return_exceptions=True
        )
        
        # Process results and collect failed translations for retry
        translated_texts = []
        failed_indices = []
        failed_texts = []
        failed_contexts = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Translation failed for text {i}: {result}")
                # Mark for retry instead of returning original immediately
                failed_indices.append(i)
                failed_texts.append(texts[i])
                failed_contexts.append(contexts[i] if i < len(contexts) else None)
                translated_texts.append(None)  # Placeholder
            else:
                translated_texts.append(result)
        
        # Retry failed translations if any
        if failed_texts:
            logger.info(f"Retrying {len(failed_texts)} failed translations...")
            await asyncio.sleep(2.0)  # Brief delay before retry
            
            retry_results = await asyncio.gather(
                *[translate_with_semaphore(
                    self.translate_text(text, target_language, source_language, context)
                ) for text, context in zip(failed_texts, failed_contexts)],
                return_exceptions=True
            )
            
            # Update results with retry attempts
            for i, (failed_idx, retry_result) in enumerate(zip(failed_indices, retry_results)):
                if isinstance(retry_result, Exception):
                    logger.error(f"Retry failed for text {failed_idx}: {retry_result}")
                    # Final fallback: return original text
                    translated_texts[failed_idx] = texts[failed_idx]
                else:
                    logger.info(f"Retry successful for text {failed_idx}")
                    translated_texts[failed_idx] = retry_result
        
        return translated_texts
    
    async def get_supported_languages(self) -> List[Dict[str, str]]:
        """
        Get list of supported languages.
        
        Returns:
            List of language dictionaries with code and name
        """
        try:
            # For now, return static list. In production, this would query DeepSeek API
            languages = [
                {"code": "es", "name": "Spanish"},
                {"code": "fr", "name": "French"},
                {"code": "de", "name": "German"},
                {"code": "it", "name": "Italian"},
                {"code": "pt", "name": "Portuguese"},
                {"code": "ru", "name": "Russian"},
                {"code": "ja", "name": "Japanese"},
                {"code": "ko", "name": "Korean"},
                {"code": "zh-CN", "name": "Simplified Chinese"},
                {"code": "zh-HK", "name": "Traditional Chinese (Hong Kong)"},
                {"code": "ar", "name": "Arabic"},
                {"code": "nl", "name": "Dutch"},
                {"code": "sv", "name": "Swedish"},
                {"code": "no", "name": "Norwegian"},
                {"code": "da", "name": "Danish"},
                {"code": "fi", "name": "Finnish"},
                {"code": "pl", "name": "Polish"},
                {"code": "cs", "name": "Czech"},
                {"code": "hu", "name": "Hungarian"},
                {"code": "ro", "name": "Romanian"},
                {"code": "bg", "name": "Bulgarian"}
            ]
            
            return languages
            
        except Exception as e:
            logger.error(f"Failed to get supported languages: {e}")
            return []
    
    async def test_connection(self) -> bool:
        """
        Test API connection and authentication.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test with a simple translation
            result = await self.translate_text("Hello", "es")
            return bool(result)
            
        except Exception as e:
            logger.error(f"DeepSeek API connection test failed: {e}")
            return False


# Global client instance
_deepseek_client: Optional[DeepSeekClient] = None


async def get_deepseek_client() -> DeepSeekClient:
    """Get or create DeepSeek client instance."""
    global _deepseek_client
    
    if _deepseek_client is None:
        _deepseek_client = DeepSeekClient()
    
    return _deepseek_client


async def cleanup_deepseek_client():
    """Cleanup DeepSeek client."""
    global _deepseek_client
    
    if _deepseek_client and _deepseek_client._client:
        await _deepseek_client._client.aclose()
        _deepseek_client = None 