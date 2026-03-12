"""
vLLM LLM Service

Supports local LLMs via vLLM server or OpenAI-compatible API.
Works with Llama, Mistral, Qwen, and other open-weight models.
"""

import logging
import json
from typing import Dict, Any, Optional, Type

from .llm_service import LLMService

logger = logging.getLogger(__name__)


class VLLMLLMService(LLMService):
    """
    LLM service for vLLM-hosted models.
    
    vLLM provides:
    - High-throughput inference
    - OpenAI-compatible API
    - Support for Llama, Mistral, Qwen, etc.
    - Local deployment (no API costs)
    
    Can also connect to any OpenAI-compatible endpoint.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "meta-llama/Llama-3.1-8B-Instruct",
        api_key: Optional[str] = None,
        timeout: int = 120
    ):
        """
        Initialize vLLM service.
        
        Args:
            base_url: vLLM server URL (default: localhost:8000)
            model: Model name as served by vLLM
            api_key: Optional API key (some deployments require it)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key or "EMPTY"  # vLLM accepts any key by default
        self.timeout = timeout
        self._client = None
        
    def _ensure_client(self):
        """Initialize OpenAI client pointing to vLLM."""
        if self._client is not None:
            return
            
        try:
            from openai import OpenAI
            
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout
            )
            logger.info(f"vLLM client initialized: {self.base_url}, model: {self.model}")
            
        except ImportError:
            logger.error("openai package required for vLLM client")
            raise ImportError("Install openai: pip install openai")
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """Generate text completion."""
        self._ensure_client()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            result = response.choices[0].message.content
            logger.debug(f"vLLM generated {len(result)} chars")
            return result
            
        except Exception as e:
            logger.error(f"vLLM generation failed: {e}")
            raise
    
    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        pydantic_model: Optional[Type] = None
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.
        
        Note: vLLM supports guided generation for JSON schemas.
        Falls back to prompt-based JSON if not available.
        """
        self._ensure_client()
        
        messages = []
        
        # Build system prompt with JSON instruction
        json_system = (
            f"{system_prompt or ''}\n\n"
            "You must respond with valid JSON only. No other text."
        )
        messages.append({"role": "system", "content": json_system})
        
        # Add schema to prompt
        schema_str = json.dumps(response_schema, indent=2) if response_schema else "{}"
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"Respond with JSON matching this schema:\n{schema_str}"
        )
        messages.append({"role": "user", "content": enhanced_prompt})
        
        try:
            # Try with response_format if supported
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
            except Exception:
                # Fallback without response_format
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.3,
                    max_tokens=1000
                )
            
            content = response.choices[0].message.content
            
            # Parse JSON from response
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from vLLM: {e}")
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise
        except Exception as e:
            logger.error(f"vLLM structured generation failed: {e}")
            raise
    
    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """Stream text generation."""
        self._ensure_client()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            stream = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"vLLM streaming failed: {e}")
            raise
    
    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model
