"""Tests for configuration management"""

import os
import pytest
from src.config import AppConfig, get_config


def test_config_from_env_defaults():
    """Test that configuration loads with default values"""
    config = AppConfig.from_env()
    
    assert config is not None
    assert config.env in ["development", "production"]
    assert config.vector_store.provider in ["chromadb", "opensearch"]
    assert config.embedding.provider in ["openai", "sentence-transformers", "cohere"]
    assert config.llm.provider in ["openai", "anthropic", "gemini"]


def test_config_validation():
    """Test configuration validation"""
    config = AppConfig.from_env()
    errors = config.validate()
    
    # Errors are expected if environment variables are not set
    assert isinstance(errors, list)


def test_get_config_singleton():
    """Test that get_config returns the same instance"""
    config1 = get_config()
    config2 = get_config()
    
    assert config1 is config2


@pytest.mark.parametrize("provider", ["chromadb", "opensearch"])
def test_vector_store_config(provider, monkeypatch):
    """Test vector store configuration for different providers"""
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", provider)
    
    config = AppConfig.from_env()
    assert config.vector_store.provider == provider
    assert isinstance(config.vector_store.config, dict)


@pytest.mark.parametrize("provider", ["openai", "sentence-transformers", "cohere"])
def test_embedding_config(provider, monkeypatch):
    """Test embedding configuration for different providers"""
    monkeypatch.setenv("EMBEDDING_PROVIDER", provider)
    
    config = AppConfig.from_env()
    assert config.embedding.provider == provider
    assert isinstance(config.embedding.config, dict)


@pytest.mark.parametrize("provider", ["openai", "anthropic", "gemini"])
def test_llm_config(provider, monkeypatch):
    """Test LLM configuration for different providers"""
    monkeypatch.setenv("LLM_PROVIDER", provider)
    
    config = AppConfig.from_env()
    assert config.llm.provider == provider
    assert isinstance(config.llm.config, dict)
