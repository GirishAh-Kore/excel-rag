"""
LLM Service Factory

Factory for creating LLM service instances based on configuration.
"""

from typing import Dict, Any
import logging
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class LLMServiceFactory:
    """Factory for creating LLM service instances"""
    
    @staticmethod
    def create(provider: str, config: Dict[str, Any]) -> LLMService:
        """
        Creates an LLM service instance based on provider
        
        Args:
            provider: Provider name ("openai", "anthropic", "gemini", "vllm", "ollama")
            config: Configuration dictionary for the provider
            
        Returns:
            LLMService instance
            
        Raises:
            ValueError: If provider is unknown or config is invalid
        """
        provider = provider.lower()
        
        try:
            if provider == "openai":
                from .openai_llm_service import OpenAILLMService
                
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("OpenAI requires 'api_key' in config")
                
                model = config.get("model", "gpt-4o")
                
                logger.info(f"Creating OpenAI LLM service with model: {model}")
                return OpenAILLMService(api_key=api_key, model=model)
            
            elif provider == "anthropic":
                from .anthropic_llm_service import AnthropicLLMService
                
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("Anthropic requires 'api_key' in config")
                
                model = config.get("model", "claude-3-5-sonnet-20241022")
                
                logger.info(f"Creating Anthropic LLM service with model: {model}")
                return AnthropicLLMService(api_key=api_key, model=model)
            
            elif provider == "gemini":
                from .gemini_llm_service import GeminiLLMService
                
                api_key = config.get("api_key")
                if not api_key:
                    raise ValueError("Gemini requires 'api_key' in config")
                
                model = config.get("model", "gemini-pro")
                
                logger.info(f"Creating Gemini LLM service with model: {model}")
                return GeminiLLMService(api_key=api_key, model=model)
            
            elif provider == "vllm":
                from .vllm_llm_service import VLLMLLMService
                
                base_url = config.get("base_url", "http://localhost:8000/v1")
                model = config.get("model", "meta-llama/Llama-3.1-8B-Instruct")
                api_key = config.get("api_key")  # Optional for vLLM
                timeout = config.get("timeout", 120)
                
                logger.info(f"Creating vLLM service: {base_url}, model: {model}")
                return VLLMLLMService(
                    base_url=base_url,
                    model=model,
                    api_key=api_key,
                    timeout=timeout
                )
            
            elif provider == "ollama":
                from .ollama_llm_service import OllamaLLMService
                
                model = config.get("model", "llama3.1")
                base_url = config.get("base_url", "http://localhost:11434")
                timeout = config.get("timeout", 120)
                
                logger.info(f"Creating Ollama service: {base_url}, model: {model}")
                return OllamaLLMService(
                    model=model,
                    base_url=base_url,
                    timeout=timeout
                )
            
            else:
                raise ValueError(
                    f"Unknown LLM provider: {provider}. "
                    f"Supported providers: 'openai', 'anthropic', 'gemini', 'vllm', 'ollama'"
                )
        
        except Exception as e:
            logger.error(f"Failed to create LLM service for provider '{provider}': {e}")
            raise
