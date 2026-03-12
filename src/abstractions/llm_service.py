"""
LLM Service Abstraction Layer

Provides a pluggable interface for language model providers,
supporting OpenAI, Anthropic, Google Gemini, and others.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class LLMService(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Generates text completion for a prompt
        
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
        Generates structured output (JSON) based on schema
        
        Args:
            prompt: User prompt/question
            response_schema: Expected JSON schema for response
            system_prompt: Optional system instructions
            
        Returns:
            Parsed JSON response matching schema
        """
        pass
        
    @abstractmethod
    def get_model_name(self) -> str:
        """
        Returns the name/identifier of the LLM
        
        Returns:
            Model name string
        """
        pass
