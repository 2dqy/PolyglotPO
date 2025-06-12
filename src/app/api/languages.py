"""
Languages API endpoints for the Translation Tool.
Handles supported languages and language-related operations.
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from ..models.api_models import LanguageInfo
from ..core.deepseek_client import get_deepseek_client
from ..config import SUPPORTED_LANGUAGES
from loguru import logger

router = APIRouter()


@router.get("/languages/supported", response_model=List[LanguageInfo])
async def get_supported_languages():
    """
    Get list of supported languages for translation.
    
    Returns:
        List of LanguageInfo with supported languages
    """
    try:
        # Try to get languages from DeepSeek API
        try:
            deepseek_client = await get_deepseek_client()
            async with deepseek_client:
                api_languages = await deepseek_client.get_supported_languages()
            
            return [
                LanguageInfo(
                    code=lang["code"],
                    name=lang["name"],
                    available=True
                )
                for lang in api_languages
            ]
            
        except Exception as e:
            logger.warning(f"Failed to get languages from DeepSeek API: {e}")
            
            # Fallback to static configuration
            return [
                LanguageInfo(
                    code=code,
                    name=name,
                    available=True
                )
                for code, name in SUPPORTED_LANGUAGES.items()
            ]
    
    except Exception as e:
        logger.error(f"Failed to get supported languages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages/{language_code}", response_model=LanguageInfo)
async def get_language_info(language_code: str):
    """
    Get information about a specific language.
    
    Args:
        language_code: Language code (e.g., 'es', 'fr')
        
    Returns:
        LanguageInfo for the specified language
    """
    try:
        # Check if language exists in our configuration
        if language_code in SUPPORTED_LANGUAGES:
            return LanguageInfo(
                code=language_code,
                name=SUPPORTED_LANGUAGES[language_code],
                available=True
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Language '{language_code}' not supported"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get language info for {language_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages/{language_code}/test")
async def test_language_translation(language_code: str):
    """
    Test translation capability for a specific language.
    
    Args:
        language_code: Language code to test
        
    Returns:
        Dict with test results
    """
    try:
        # Check if language is supported
        if language_code not in SUPPORTED_LANGUAGES:
            raise HTTPException(
                status_code=404,
                detail=f"Language '{language_code}' not supported"
            )
        
        # Test translation with a simple phrase
        test_text = "Hello, world!"
        
        try:
            deepseek_client = await get_deepseek_client()
            async with deepseek_client:
                translated_text = await deepseek_client.translate_text(
                    text=test_text,
                    target_language=language_code,
                    source_language="en"
                )
            
            success = bool(translated_text and translated_text != test_text)
            
            return {
                "language_code": language_code,
                "language_name": SUPPORTED_LANGUAGES[language_code],
                "test_successful": success,
                "test_input": test_text,
                "test_output": translated_text,
                "message": "Translation test successful" if success else "Translation test failed"
            }
            
        except Exception as e:
            logger.warning(f"Translation test failed for {language_code}: {e}")
            
            return {
                "language_code": language_code,
                "language_name": SUPPORTED_LANGUAGES[language_code],
                "test_successful": False,
                "test_input": test_text,
                "test_output": None,
                "error": str(e),
                "message": "Translation API unavailable"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test language {language_code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages/stats", response_model=Dict[str, Any])
async def get_language_usage_stats():
    """
    Get usage statistics for supported languages.
    
    Returns:
        Dict with language usage statistics
    """
    try:
        from ..core.translation_service import get_translation_service
        
        translation_service = get_translation_service()
        jobs = translation_service.get_all_jobs()
        
        # Count usage by target language
        language_usage = {}
        total_jobs = len(jobs)
        
        for job in jobs:
            target_lang = job.target_language
            if target_lang in language_usage:
                language_usage[target_lang] += 1
            else:
                language_usage[target_lang] = 1
        
        # Calculate percentages and add language names
        language_stats = []
        for lang_code, count in language_usage.items():
            percentage = (count / total_jobs * 100) if total_jobs > 0 else 0
            
            language_stats.append({
                "code": lang_code,
                "name": SUPPORTED_LANGUAGES.get(lang_code, lang_code),
                "usage_count": count,
                "usage_percentage": round(percentage, 1)
            })
        
        # Sort by usage count (descending)
        language_stats.sort(key=lambda x: x["usage_count"], reverse=True)
        
        return {
            "total_jobs": total_jobs,
            "languages_used": len(language_usage),
            "language_stats": language_stats,
            "most_popular": language_stats[0] if language_stats else None
        }
    
    except Exception as e:
        logger.error(f"Failed to get language usage stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/languages/check-api")
async def check_translation_api():
    """
    Check the status and connectivity of the translation API.
    
    Returns:
        Dict with API status information
    """
    try:
        deepseek_client = await get_deepseek_client()
        
        # Test API connectivity
        try:
            api_available = await deepseek_client.test_connection()
            
            if api_available:
                # Get supported languages count
                async with deepseek_client:
                    supported_languages = await deepseek_client.get_supported_languages()
                
                return {
                    "api_available": True,
                    "status": "healthy",
                    "supported_languages_count": len(supported_languages),
                    "message": "Translation API is working properly"
                }
            else:
                return {
                    "api_available": False,
                    "status": "unhealthy",
                    "supported_languages_count": 0,
                    "message": "Translation API is not responding"
                }
                
        except Exception as e:
            logger.error(f"Translation API health check failed: {e}")
            
            return {
                "api_available": False,
                "status": "error",
                "error": str(e),
                "message": "Translation API health check failed",
                "fallback_available": True,
                "fallback_languages_count": len(SUPPORTED_LANGUAGES)
            }
    
    except Exception as e:
        logger.error(f"Failed to check translation API: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 