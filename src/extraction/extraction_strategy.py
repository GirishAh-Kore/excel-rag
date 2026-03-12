"""
Extraction strategy definitions and configuration.

This module defines different extraction strategies and their configuration.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionStrategy(str, Enum):
    """Available extraction strategies for Excel files."""
    
    OPENPYXL = "openpyxl"          # Default: Fast, free, local processing
    GEMINI = "gemini"              # Google Gemini: Multimodal understanding
    LLAMAPARSE = "llamaparse"      # LlamaParse: Document understanding
    DOCLING = "docling"            # IBM Docling: Open-source document understanding
    UNSTRUCTURED = "unstructured"  # Unstructured.io: Document chunking for RAG
    AUTO = "auto"                  # Automatically choose best strategy


class ExtractionConfig(BaseModel):
    """Configuration for extraction strategies."""
    
    # Primary extraction settings
    default_strategy: ExtractionStrategy = Field(
        default=ExtractionStrategy.OPENPYXL,
        description="Default extraction strategy to use"
    )
    max_rows_per_sheet: int = Field(
        default=10000,
        ge=1,
        description="Maximum rows to process per sheet"
    )
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        description="Maximum file size in MB"
    )
    
    # LLM Summarization
    enable_llm_summarization: bool = Field(
        default=True,
        description="Generate LLM summaries for sheets during indexing"
    )
    summarization_provider: str = Field(
        default="openai",
        description="LLM provider for summarization (openai, anthropic, gemini)"
    )
    summarization_model: Optional[str] = Field(
        default=None,
        description="Specific model for summarization (e.g., gpt-4o-mini)"
    )
    summarization_max_tokens: int = Field(
        default=150,
        ge=50,
        le=500,
        description="Max tokens for summary generation"
    )
    
    # Google Gemini settings
    enable_gemini: bool = Field(
        default=False,
        description="Enable Google Gemini for extraction"
    )
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key"
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        description="Gemini model to use"
    )
    gemini_fallback_on_error: bool = Field(
        default=True,
        description="Use Gemini as fallback when openpyxl fails"
    )
    
    # LlamaParse settings
    enable_llamaparse: bool = Field(
        default=False,
        description="Enable LlamaParse for extraction"
    )
    llamaparse_api_key: Optional[str] = Field(
        default=None,
        description="LlamaParse API key"
    )
    
    # Docling settings (IBM open-source)
    enable_docling: bool = Field(
        default=False,
        description="Enable IBM Docling for extraction (open-source)"
    )
    docling_model: str = Field(
        default="default",
        description="Docling model variant to use"
    )
    
    # Unstructured.io settings (open-source, runs locally)
    enable_unstructured: bool = Field(
        default=False,
        description="Enable Unstructured.io for extraction (open-source, local)"
    )
    unstructured_api_key: Optional[str] = Field(
        default=None,
        description="Unstructured.io API key (only for hosted SaaS, not needed for local)"
    )
    unstructured_api_url: Optional[str] = Field(
        default=None,
        description="Unstructured.io API URL (only for self-hosted API server)"
    )
    unstructured_strategy: str = Field(
        default="auto",
        description="Unstructured partition strategy (auto, fast, hi_res)"
    )
    
    # Smart extraction rules
    use_auto_strategy: bool = Field(
        default=False,
        description="Automatically choose best extraction strategy"
    )
    complexity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Complexity score threshold for using advanced extractors"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "default_strategy": "openpyxl",
                "enable_llm_summarization": True,
                "summarization_provider": "openai",
                "enable_gemini": False,
                "gemini_fallback_on_error": True
            }
        }


class ExtractionQuality(BaseModel):
    """Quality metrics for extraction results."""
    
    score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    has_headers: bool = Field(..., description="Headers were detected")
    has_data: bool = Field(..., description="Data rows were extracted")
    data_completeness: float = Field(..., ge=0.0, le=1.0, description="Percentage of non-empty cells")
    structure_clarity: float = Field(..., ge=0.0, le=1.0, description="How clear the structure is")
    extraction_errors: int = Field(default=0, ge=0, description="Number of errors during extraction")
    
    @property
    def is_high_quality(self) -> bool:
        """Check if extraction quality is high enough."""
        return (
            self.score >= 0.7 and
            self.has_headers and
            self.has_data and
            self.extraction_errors == 0
        )
