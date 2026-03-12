"""
OpenAI LLM Service Implementation

Supports OpenAI's GPT models with streaming and structured outputs (Pydantic).
"""

from typing import Dict, Any, Optional, Type
import logging
import json
from .llm_service import LLMService

logger = logging.getLogger(__name__)


class OpenAILLMService(LLMService):
    """OpenAI LLM implementation with structured output support."""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """
        Initialize OpenAI LLM service.

        Args:
            api_key: OpenAI API key
            model: Model name (gpt-4o, gpt-4o-mini, etc.)
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
        """Generate text completion for a prompt."""
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
        system_prompt: Optional[str] = None,
        pydantic_model: Optional[Type] = None
    ) -> Dict[str, Any]:
        """
        Generate structured JSON output.

        Prefers the native Pydantic structured-output API when a pydantic_model
        is supplied (requires openai>=1.51.0 and a model that supports it).
        Falls back to json_object mode otherwise.
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            if pydantic_model is not None:
                # Use beta structured outputs with Pydantic schema
                messages.append({"role": "user", "content": prompt})
                response = self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=messages,
                    response_format=pydantic_model,
                    temperature=0.3
                )
                parsed = response.choices[0].message.parsed
                return parsed.model_dump() if hasattr(parsed, "model_dump") else dict(parsed)

            # Fallback: json_object mode
            enhanced_prompt = (
                f"{prompt}\n\nRespond with valid JSON matching this schema: "
                f"{json.dumps(response_schema)}"
            )
            messages.append({"role": "user", "content": enhanced_prompt})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content)
            logger.debug("Generated structured response")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to generate structured response: {e}")
            raise

    def get_model_name(self) -> str:
        """Return the model name."""
        return self.model

    def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ):
        """
        Generate text with streaming.

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
