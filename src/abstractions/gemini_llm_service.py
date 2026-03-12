"""
Google Gemini LLM Service Implementation

Supports Google's Gemini models.
"""

from typing import Dict, Any, Optional
import logging
import json
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class GeminiLLMService(LLMService):
    """Google Gemini implementation"""
    
    def __init__(self, api_key: str, model: str = "gemini-pro"):
        """
        Initialize Gemini LLM service
        
        Args:
            api_key: Google API key
            model: Model name (gemini-pro, gemini-pro-vision, etc.)
        """
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(model)
            self.model_name = model
            logger.info(f"Gemini LLM service initialized with model: {model}")
        except ImportError:
            logger.error("google-generativeai package not installed. Install with: pip install google-generativeai")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Gemini LLM service: {e}")
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
            # Gemini doesn't have separate system prompt, so we prepend it
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }
            
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config
            )
            
            result = response.text
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
        return self.model_name
    
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
            full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }
            
            response = self.model.generate_content(
                full_prompt,
                generation_config=generation_config,
                stream=True
            )
            
            for chunk in response:
                if chunk.text:
                    yield chunk.text
        
        except Exception as e:
            logger.error(f"Failed to stream response: {e}")
            raise
