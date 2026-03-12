"""
Ollama LLM Service

Supports local LLMs via Ollama for easy local deployment.
Works with Llama, Mistral, Qwen, Phi, and other models.
"""

import logging
import json
from typing import Dict, Any, Optional, Type

from .llm_service import LLMService

logger = logging.getLogger(__name__)


class OllamaLLMService(LLMService):
    """
    LLM service for Ollama-hosted models.
    
    Ollama provides:
    - Simple local model management
    - Easy model pulling (ollama pull llama3.1)
    - Low resource usage
    - Support for many open models
    """
    
    def __init__(
        self,
        model: str = "llama3.1",
        base_url: str = "http://localhost:11434",
        timeout: int = 120
    ):
        """
        Initialize Ollama service.
        
        Args:
            model: Model name (e.g., llama3.1, mistral, qwen2.5)
            base_url: Ollama server URL
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._client = None
        
    def _ensure_client(self):
        """Initialize Ollama client."""
        if self._client is not None:
            return
            
        try:
            import ollama
            self._client = ollama.Client(host=self.base_url)
            logger.info(f"Ollama client initialized: {self.base_url}, model: {self.model}")
            
        except ImportError:
            # Fallback to requests
            logger.info("Using requests for Ollama API")
            self._client = "requests"
    
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
            if self._client == "requests":
                return self._generate_via_requests(messages, temperature, max_tokens)
            
            response = self._client.chat(
                model=self.model,
                messages=messages,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            )
            
            result = response['message']['content']
            logger.debug(f"Ollama generated {len(result)} chars")
            return result
            
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            raise
    
    def _generate_via_requests(
        self,
        messages: list,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate using requests library."""
        import requests
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                },
                "stream": False
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        
        return response.json()['message']['content']
    
    def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        pydantic_model: Optional[Type] = None
    ) -> Dict[str, Any]:
        """Generate structured JSON output."""
        self._ensure_client()
        
        # Build JSON-focused prompt
        json_system = (
            f"{system_prompt or ''}\n\n"
            "You must respond with valid JSON only. No markdown, no explanation."
        )
        
        schema_str = json.dumps(response_schema, indent=2) if response_schema else "{}"
        enhanced_prompt = (
            f"{prompt}\n\n"
            f"Respond with JSON matching this schema:\n{schema_str}"
        )
        
        messages = [
            {"role": "system", "content": json_system},
            {"role": "user", "content": enhanced_prompt}
        ]
        
        try:
            if self._client == "requests":
                content = self._generate_via_requests(messages, 0.3, 1000)
            else:
                # Use format parameter for JSON mode if available
                try:
                    response = self._client.chat(
                        model=self.model,
                        messages=messages,
                        format="json",
                        options={"temperature": 0.3, "num_predict": 1000}
                    )
                    content = response['message']['content']
                except Exception:
                    # Fallback without format
                    response = self._client.chat(
                        model=self.model,
                        messages=messages,
                        options={"temperature": 0.3, "num_predict": 1000}
                    )
                    content = response['message']['content']
            
            # Parse JSON
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Ollama: {e}")
            # Try to extract JSON
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise
        except Exception as e:
            logger.error(f"Ollama structured generation failed: {e}")
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
            if self._client == "requests":
                # Stream via requests
                import requests
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "options": {
                            "temperature": temperature,
                            "num_predict": max_tokens
                        },
                        "stream": True
                    },
                    stream=True,
                    timeout=self.timeout
                )
                
                for line in response.iter_lines():
                    if line:
                        data = json.loads(line)
                        if 'message' in data and 'content' in data['message']:
                            yield data['message']['content']
            else:
                stream = self._client.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": temperature,
                        "num_predict": max_tokens
                    },
                    stream=True
                )
                
                for chunk in stream:
                    if 'message' in chunk and 'content' in chunk['message']:
                        yield chunk['message']['content']
                        
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            raise
    
    def get_model_name(self) -> str:
        """Return the model name."""
        return f"ollama/{self.model}"
    
    def list_models(self) -> list:
        """List available models in Ollama."""
        self._ensure_client()
        
        if self._client == "requests":
            import requests
            response = requests.get(f"{self.base_url}/api/tags")
            return [m['name'] for m in response.json().get('models', [])]
        
        return [m['name'] for m in self._client.list()['models']]
