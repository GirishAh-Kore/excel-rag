"""
LLM Service Factory

Factory for creating LLM service instances based on configuration.
"""

from typing import Dict, Any
import logging
from .llm_service import LLMService
from .openai_llm_service import OpenAILLMService
from .anthropic_llm_service import AnthropicLLMService
from .gemini_llm_service import GeminiLLMService

logger = logging.getLogger(__name__)


class LLMServiceFactory:
    """Factory for creating LLM service instances"""
    
    @staticmethod
    def create(provider: str, config: Dict[str, Any]) -> LLMService:
        """
        Creates an LLM service instance based on provider
        
        Args:
            provider: Provider name ("openai", "anthropic", "gemini")
            config: Configuration dictionary for the provider
            
        Returns:
            LLMService instance
            
        Raises:
            ValueError: If provider is unknown or config is invalid
        """
        provider = provider.lower()
        
        try:
            if provider == "openai":
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("OpenAI requires 'api_key' in config")
                
                model = config.get("model", "gpt-4")
                
                logger.info(f"Creating OpenAI LLM service with model: {model}")
                return OpenAILLMService(api_key=api_key, model=model)
            
            elif provider == "anthropic":
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("Anthropic requires 'api_key' in config")
                
                model = config.get("model", "claude-3-5-sonnet-20241022")
                
                logger.info(f"Creating Anthropic LLM service with model: {model}")
                return AnthropicLLMService(api_key=api_key, model=model)
            
            elif provider == "gemini":
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("Gemini requires 'api_key' in config")
                
                model = config.get("model", "gemini-pro")
                
                logger.info(f"Creating Gemini LLM service with model: {model}")
                return GeminiLLMService(api_key=api_key, model=model)
            
            else:
                raise ValueError(
                    f"Unknown LLM provider: {provider}. "
                    f"Supported providers: 'openai', 'anthropic', 'gemini'"
                )
        
        except Exception as e:
            logger.error(f"Failed to create LLM service for provider '{provider}': {e}")
            raise
