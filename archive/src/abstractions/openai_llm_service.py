"""
OpenAI LLM Service Implementation

Supports OpenAI's GPT models with streaming support.
"""

from typing import Dict, Any, Optional
import logging
import json
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class OpenAILLMService(LLMService):
    """OpenAI LLM implementation"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize OpenAI LLM service
        
        Args:
            api_key: OpenAI API key
            model: Model name (gpt-4, gpt-4-turbo, gpt-3.5-turbo, etc.)
        """
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
            self.model = model
            logger.info(f"OpenAI LLM service initialized with model: {model}")
        except ImportError:
            logger.error("openai package not installed. Install with: pip install openai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI LLM service: {e}")
            raise
        
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generates text completion for a prompt"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            result = response.choices[0].message.content
            logger.debug(f"Generated response with {len(result)} characters")
            return result
        
        except Exception as e:
            logger.error(f"Failed to generate response: {e}")
            raise
        
    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates structured output (JSON) based on schema"""
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add schema information to prompt
            enhanced_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_schema)}"
            messages.append({"role": "user", "content": enhanced_prompt})
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3  # Lower temperature for structured output
            )
            
            result = json.loads(response.choices[0].message.content)
            logger.debug(f"Generated structured response")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate structured response: {e}")
            raise
        
    def get_model_name(self) -> str:
        """Returns the model name"""
        return self.model
    
    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """
        Generates text completion with streaming
        
        Args:
            prompt: User prompt/question
            system_prompt: Optional system instructions
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            
        Yields:
            Text chunks as they are generated
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        
        except Exception as e:
            logger.error(f"Failed to stream response: {e}")
            raise
