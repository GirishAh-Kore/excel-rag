"""
LLM Service Abstraction Layer

Provides a pluggable interface for language model providers,
supporting OpenAI, Anthropic, Google Gemini, vLLM, Ollama, and others.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Generator
import logging

logger = logging.getLogger(__name__)


class LLMService(ABC):
    """
    Abstract base class for LLM providers.
    
    All LLM implementations must inherit from this class and implement
    all abstract methods. This ensures consistent behavior across
    different providers (OpenAI, Anthropic, Gemini, vLLM, Ollama).
    
    Example:
        class MyLLMService(LLMService):
            def generate(self, prompt, ...): ...
            def generate_structured(self, prompt, ...): ...
            def stream_generate(self, prompt, ...): ...
            def get_model_name(self): ...
    """
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generate text completion for a prompt.
        
        Args:
            prompt: User prompt/question
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate structured output (JSON) based on schema.
        
        Args:
            prompt: User prompt/question
            response_schema: Expected JSON schema for response
            system_prompt: Optional system instructions
            
        Returns:
            Parsed JSON response matching schema
        """
        pass
    
    @abstractmethod
    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> Generator[str, None, None]:
        """
        Stream text generation token by token.
        
        This method enables real-time streaming of generated text,
        useful for providing immediate feedback to users.
        
        Args:
            prompt: User prompt/question
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            
        Yields:
            Generated text chunks as they become available
            
        Example:
            for chunk in llm_service.stream_generate("Hello"):
                print(chunk, end="", flush=True)
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """
        Return the name/identifier of the LLM.
        
        Returns:
            Model name string (e.g., "gpt-4o", "claude-3-5-sonnet")
        """
        pass
