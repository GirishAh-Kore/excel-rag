"""
Anthropic LLM Service Implementation

Supports Anthropic's Claude models with streaming support.
"""

from typing import Dict, Any, Optional
import logging
import json
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class AnthropicLLMService(LLMService):
    """Anthropic Claude implementation"""
    
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Anthropic LLM service
        
        Args:
            api_key: Anthropic API key
            model: Model name (claude-3-5-sonnet-20241022, claude-3-opus-20240229, etc.)
        """
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = model
            logger.info(f"Anthropic LLM service initialized with model: {model}")
        except ImportError:
            logger.error("anthropic package not installed. Install with: pip install anthropic")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic LLM service: {e}")
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
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}]
            )
            
            result = response.content[0].text
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
            # Claude doesn't have native JSON mode, so we enhance the prompt
            enhanced_prompt = (
                f"{prompt}\n\n"
                f"Respond with valid JSON only, matching this schema: {json.dumps(response_schema)}\n"
                f"Do not include any text before or after the JSON."
            )
            
            response_text = self.generate(
                enhanced_prompt,
                system_prompt,
                temperature=0.3,  # Lower temperature for structured output
                max_tokens=2000
            )
            
            # Try to extract JSON if there's extra text
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            result = json.loads(response_text)
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
            with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt or "",
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    yield text
        
        except Exception as e:
            logger.error(f"Failed to stream response: {e}")
            raise
