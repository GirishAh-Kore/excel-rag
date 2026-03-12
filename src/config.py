"""Configuration management for the application"""

import os
from dataclasses import dataclass
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class VectorStoreConfig:
    """Configuration for vector store"""
    provider: str
    config: Dict[str, Any]


@dataclass
class EmbeddingConfig:
    """Configuration for embedding service"""
    provider: str
    config: Dict[str, Any]


@dataclass
class LLMConfig:
    """Configuration for LLM service"""
    provider: str
    config: Dict[str, Any]


@dataclass
class GoogleDriveConfig:
    """Configuration for Google Drive OAuth"""
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]
    token_storage_path: str
    token_encryption_key: str


@dataclass
class DatabaseConfig:
    """Configuration for SQLite database"""
    db_path: str


@dataclass
class ExtractionConfig:
    """Configuration for Excel extraction"""
    default_strategy: str
    max_rows_per_sheet: int
    max_file_size_mb: int
    enable_llm_summarization: bool
    summarization_provider: str
    summarization_model: Optional[str]
    summarization_max_tokens: int
    enable_gemini: bool
    gemini_api_key: Optional[str]
    gemini_model: str
    gemini_fallback_on_error: bool
    enable_llamaparse: bool
    llamaparse_api_key: Optional[str]
    use_auto_strategy: bool
    complexity_threshold: float


@dataclass
class IndexingConfig:
    """Configuration for indexing pipeline"""
    max_concurrent_files: int
    batch_size: int


@dataclass
class QueryConfig:
    """Configuration for query processing"""
    session_timeout_minutes: int
    top_k_results: int
    confidence_threshold: float
    # Reranking
    enable_reranking: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Hybrid search
    enable_hybrid_search: bool = True
    # HyDE query expansion
    enable_hyde: bool = True
    # Split models for analysis vs generation
    analysis_model: str = "gpt-4o-mini"
    generation_model: str = "gpt-4o"
    # Streaming
    enable_streaming: bool = True


@dataclass
class APIConfig:
    """Configuration for API server"""
    host: str
    port: int
    rate_limit: int
    cors_origins: list[str]


@dataclass
class LanguageConfig:
    """Configuration for language processing"""
    supported_languages: list[str]
    default_language: str
    enable_language_detection: bool
    language_detection_confidence_threshold: float
    enable_lemmatization: bool
    enable_thai_tokenization: bool
    thai_tokenizer_engine: str
    semantic_match_threshold: float
    enable_keyword_fallback: bool
    enable_fuzzy_matching: bool
    fuzzy_match_threshold: float
    preprocess_before_embedding: bool


@dataclass
class CacheConfig:
    """Configuration for caching"""
    backend: str
    config: Dict[str, Any]


@dataclass
class AppConfig:
    """Main application configuration"""
    env: str
    log_level: str
    vector_store: VectorStoreConfig
    embedding: EmbeddingConfig
    llm: LLMConfig
    google_drive: GoogleDriveConfig
    database: DatabaseConfig
    cache: CacheConfig
    extraction: ExtractionConfig
    indexing: IndexingConfig
    query: QueryConfig
    api: APIConfig
    language: LanguageConfig
    
    @classmethod
    def from_env(cls) -> 'AppConfig':
        """Load configuration from environment variables"""
        
        # Vector Store Configuration
        vector_store_provider = os.getenv("VECTOR_STORE_PROVIDER", "chromadb")
        vector_store_config = {}
        
        if vector_store_provider == "chromadb":
            vector_store_config = {
                "persist_directory": os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
            }
        elif vector_store_provider == "opensearch":
            vector_store_config = {
                "host": os.getenv("OPENSEARCH_HOST", "localhost"),
                "port": int(os.getenv("OPENSEARCH_PORT", "9200")),
                "username": os.getenv("OPENSEARCH_USERNAME", "admin"),
                "password": os.getenv("OPENSEARCH_PASSWORD", "admin")
            }
        
        # Embedding Configuration
        embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai")
        embedding_config = {
            "api_key": os.getenv("EMBEDDING_API_KEY"),
            "model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            # BGE-specific options
            "use_fp16": os.getenv("EMBEDDING_USE_FP16", "true").lower() == "true",
            "device": os.getenv("EMBEDDING_DEVICE"),  # cuda, cpu, mps, or None for auto
            "max_length": int(os.getenv("EMBEDDING_MAX_LENGTH", "8192"))
        }
        
        # LLM Configuration
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        llm_config = {
            "api_key": os.getenv("LLM_API_KEY"),
            "model": os.getenv("LLM_MODEL", "gpt-4o"),
            # vLLM/Ollama options
            "base_url": os.getenv("LLM_BASE_URL"),
            "timeout": int(os.getenv("LLM_TIMEOUT", "120"))
        }
        
        # Google Drive Configuration
        scopes_str = os.getenv("GOOGLE_SCOPES", "https://www.googleapis.com/auth/drive.readonly")
        scopes = [s.strip() for s in scopes_str.split(",")]
        
        google_drive_config = GoogleDriveConfig(
            client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
            redirect_uri=os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback"),
            scopes=scopes,
            token_storage_path=os.getenv("TOKEN_STORAGE_PATH", "./tokens"),
            token_encryption_key=os.getenv("TOKEN_ENCRYPTION_KEY", "")
        )
        
        return cls(
            env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            vector_store=VectorStoreConfig(
                provider=vector_store_provider,
                config=vector_store_config
            ),
            embedding=EmbeddingConfig(
                provider=embedding_provider,
                config=embedding_config
            ),
            llm=LLMConfig(
                provider=llm_provider,
                config=llm_config
            ),
            google_drive=google_drive_config,
            database=DatabaseConfig(
                db_path=os.getenv("SQLITE_DB_PATH", "./data/metadata.db")
            ),
            extraction=ExtractionConfig(
                default_strategy=os.getenv("EXTRACTION_STRATEGY", "openpyxl"),
                max_rows_per_sheet=int(os.getenv("MAX_ROWS_PER_SHEET", "10000")),
                max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "100")),
                enable_llm_summarization=os.getenv("ENABLE_LLM_SUMMARIZATION", "true").lower() == "true",
                summarization_provider=os.getenv("SUMMARIZATION_PROVIDER", "openai"),
                summarization_model=os.getenv("SUMMARIZATION_MODEL"),
                summarization_max_tokens=int(os.getenv("SUMMARIZATION_MAX_TOKENS", "150")),
                enable_gemini=os.getenv("ENABLE_GEMINI_EXTRACTION", "false").lower() == "true",
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                gemini_model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
                gemini_fallback_on_error=os.getenv("GEMINI_FALLBACK_ON_ERROR", "true").lower() == "true",
                enable_llamaparse=os.getenv("ENABLE_LLAMAPARSE", "false").lower() == "true",
                llamaparse_api_key=os.getenv("LLAMAPARSE_API_KEY"),
                # Docling (open-source)
                enable_docling=os.getenv("ENABLE_DOCLING", "false").lower() == "true",
                docling_model=os.getenv("DOCLING_MODEL", "default"),
                # Unstructured.io
                enable_unstructured=os.getenv("ENABLE_UNSTRUCTURED", "false").lower() == "true",
                unstructured_api_key=os.getenv("UNSTRUCTURED_API_KEY"),
                unstructured_api_url=os.getenv("UNSTRUCTURED_API_URL"),
                unstructured_strategy=os.getenv("UNSTRUCTURED_STRATEGY", "auto"),
                use_auto_strategy=os.getenv("USE_AUTO_EXTRACTION_STRATEGY", "false").lower() == "true",
                complexity_threshold=float(os.getenv("EXTRACTION_COMPLEXITY_THRESHOLD", "0.7"))
            ),
            indexing=IndexingConfig(
                max_concurrent_files=int(os.getenv("MAX_CONCURRENT_FILES", "5")),
                batch_size=int(os.getenv("BATCH_SIZE", "100"))
            ),
            query=QueryConfig(
                session_timeout_minutes=int(os.getenv("SESSION_TIMEOUT_MINUTES", "30")),
                top_k_results=int(os.getenv("TOP_K_RESULTS", "10")),
                confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.7")),
                enable_reranking=os.getenv("ENABLE_RERANKING", "true").lower() == "true",
                reranker_model=os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
                enable_hybrid_search=os.getenv("ENABLE_HYBRID_SEARCH", "true").lower() == "true",
                enable_hyde=os.getenv("ENABLE_HYDE", "true").lower() == "true",
                analysis_model=os.getenv("ANALYSIS_MODEL", "gpt-4o-mini"),
                generation_model=os.getenv("GENERATION_MODEL", "gpt-4o"),
                enable_streaming=os.getenv("ENABLE_STREAMING", "true").lower() == "true"
            ),
            api=APIConfig(
                host=os.getenv("API_HOST", "0.0.0.0"),
                port=int(os.getenv("API_PORT", "8000")),
                rate_limit=int(os.getenv("API_RATE_LIMIT", "100")),
                cors_origins=[s.strip() for s in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
            ),
            language=LanguageConfig(
                supported_languages=[s.strip() for s in os.getenv("SUPPORTED_LANGUAGES", "en,th").split(",")],
                default_language=os.getenv("DEFAULT_LANGUAGE", "en"),
                enable_language_detection=os.getenv("ENABLE_LANGUAGE_DETECTION", "true").lower() == "true",
                language_detection_confidence_threshold=float(os.getenv("LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD", "0.8")),
                enable_lemmatization=os.getenv("ENABLE_LEMMATIZATION", "true").lower() == "true",
                enable_thai_tokenization=os.getenv("ENABLE_THAI_TOKENIZATION", "true").lower() == "true",
                thai_tokenizer_engine=os.getenv("THAI_TOKENIZER_ENGINE", "newmm"),
                semantic_match_threshold=float(os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.7")),
                enable_keyword_fallback=os.getenv("ENABLE_KEYWORD_FALLBACK", "true").lower() == "true",
                enable_fuzzy_matching=os.getenv("ENABLE_FUZZY_MATCHING", "true").lower() == "true",
                fuzzy_match_threshold=float(os.getenv("FUZZY_MATCH_THRESHOLD", "0.85")),
                preprocess_before_embedding=os.getenv("PREPROCESS_BEFORE_EMBEDDING", "true").lower() == "true"
            ),
            cache=cls._load_cache_config()
        )
    
    @classmethod
    def _load_cache_config(cls) -> CacheConfig:
        """Load cache configuration from environment"""
        cache_backend = os.getenv("CACHE_BACKEND", "memory")
        cache_config = {}
        
        if cache_backend == "redis":
            cache_config = {
                "host": os.getenv("REDIS_HOST", "localhost"),
                "port": int(os.getenv("REDIS_PORT", "6379")),
                "db": int(os.getenv("REDIS_DB", "0")),
                "password": os.getenv("REDIS_PASSWORD"),
                "prefix": os.getenv("REDIS_KEY_PREFIX", "rag:"),
                "serializer": os.getenv("REDIS_SERIALIZER", "json")
            }
        elif cache_backend == "memory":
            cache_config = {
                "max_size": int(os.getenv("MEMORY_CACHE_MAX_SIZE", "1000")),
                "default_ttl": int(os.getenv("MEMORY_CACHE_DEFAULT_TTL", "3600"))
            }
        
        return CacheConfig(backend=cache_backend, config=cache_config)
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate Google Drive OAuth
        if not self.google_drive.client_id:
            errors.append("GOOGLE_CLIENT_ID is required for Google Drive authentication")
        if not self.google_drive.client_secret:
            errors.append("GOOGLE_CLIENT_SECRET is required for Google Drive authentication")
        if not self.google_drive.token_encryption_key:
            errors.append("TOKEN_ENCRYPTION_KEY is required for secure token storage")
        elif len(self.google_drive.token_encryption_key) < 32:
            errors.append("TOKEN_ENCRYPTION_KEY must be at least 32 characters long")
        
        # Validate API keys based on provider
        if self.embedding.provider == "openai":
            if not self.embedding.config.get("api_key"):
                errors.append("EMBEDDING_API_KEY is required for OpenAI embeddings")
        elif self.embedding.provider == "cohere":
            if not self.embedding.config.get("api_key"):
                errors.append("EMBEDDING_API_KEY is required for Cohere embeddings")
        elif self.embedding.provider == "sentence-transformers":
            # No API key needed for local models
            pass
        else:
            errors.append(f"Unknown embedding provider: {self.embedding.provider}")
        
        if self.llm.provider == "openai":
            if not self.llm.config.get("api_key"):
                errors.append("LLM_API_KEY is required for OpenAI LLM")
        elif self.llm.provider == "anthropic":
            if not self.llm.config.get("api_key"):
                errors.append("LLM_API_KEY is required for Anthropic LLM")
        elif self.llm.provider == "gemini":
            if not self.llm.config.get("api_key"):
                errors.append("LLM_API_KEY is required for Gemini LLM")
        else:
            errors.append(f"Unknown LLM provider: {self.llm.provider}")
        
        # Validate vector store config
        if self.vector_store.provider == "chromadb":
            if not self.vector_store.config.get("persist_directory"):
                errors.append("CHROMA_PERSIST_DIR is required for ChromaDB")
        elif self.vector_store.provider == "opensearch":
            if not self.vector_store.config.get("host"):
                errors.append("OPENSEARCH_HOST is required for OpenSearch")
            if not self.vector_store.config.get("username"):
                errors.append("OPENSEARCH_USERNAME is required for OpenSearch")
            if not self.vector_store.config.get("password"):
                errors.append("OPENSEARCH_PASSWORD is required for OpenSearch")
        else:
            errors.append(f"Unknown vector store provider: {self.vector_store.provider}")
        
        # Validate numeric ranges
        if self.indexing.max_concurrent_files < 1:
            errors.append("MAX_CONCURRENT_FILES must be at least 1")
        if self.indexing.max_rows_per_sheet < 100:
            errors.append("MAX_ROWS_PER_SHEET must be at least 100")
        if self.indexing.batch_size < 1:
            errors.append("BATCH_SIZE must be at least 1")
        if self.query.confidence_threshold < 0 or self.query.confidence_threshold > 1:
            errors.append("CONFIDENCE_THRESHOLD must be between 0 and 1")
        
        # Validate language configuration
        supported_langs = {"en", "th"}
        for lang in self.language.supported_languages:
            if lang not in supported_langs:
                errors.append(f"Unsupported language: {lang}. Supported languages: {', '.join(supported_langs)}")
        
        if self.language.default_language not in self.language.supported_languages:
            errors.append(f"DEFAULT_LANGUAGE must be one of SUPPORTED_LANGUAGES")
        
        if self.language.language_detection_confidence_threshold < 0 or self.language.language_detection_confidence_threshold > 1:
            errors.append("LANGUAGE_DETECTION_CONFIDENCE_THRESHOLD must be between 0 and 1")
        
        if self.language.semantic_match_threshold < 0 or self.language.semantic_match_threshold > 1:
            errors.append("SEMANTIC_MATCH_THRESHOLD must be between 0 and 1")
        
        if self.language.fuzzy_match_threshold < 0 or self.language.fuzzy_match_threshold > 1:
            errors.append("FUZZY_MATCH_THRESHOLD must be between 0 and 1")
        
        thai_engines = {"newmm", "longest", "deepcut"}
        if self.language.thai_tokenizer_engine not in thai_engines:
            errors.append(f"THAI_TOKENIZER_ENGINE must be one of: {', '.join(thai_engines)}")
        
        # Validate cache configuration
        cache_backends = {"redis", "memory"}
        if self.cache.backend not in cache_backends:
            errors.append(f"CACHE_BACKEND must be one of: {', '.join(cache_backends)}")
        
        if self.cache.backend == "redis":
            if not self.cache.config.get("host"):
                errors.append("REDIS_HOST is required for Redis cache")
        
        return errors
    
    def validate_and_raise(self):
        """Validate configuration and raise exception if invalid"""
        errors = self.validate()
        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {err}" for err in errors)
            raise ValueError(error_msg)


# Global configuration instance
config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or create global configuration instance"""
    global config
    if config is None:
        config = AppConfig.from_env()
    return config


def reload_config() -> AppConfig:
    """Reload configuration from environment"""
    global config
    config = AppConfig.from_env()
    return config


# CLI for configuration validation
if __name__ == "__main__":
    import sys
    
    print("Loading configuration from environment...")
    try:
        config = AppConfig.from_env()
        print(f"\n✓ Configuration loaded successfully")
        print(f"  Environment: {config.env}")
        print(f"  Log Level: {config.log_level}")
        print(f"  Vector Store: {config.vector_store.provider}")
        print(f"  Embedding Provider: {config.embedding.provider}")
        print(f"  LLM Provider: {config.llm.provider}")
        
        print("\nValidating configuration...")
        errors = config.validate()
        
        if errors:
            print(f"\n✗ Configuration validation failed with {len(errors)} error(s):")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        else:
            print("\n✓ Configuration is valid!")
            print("\nConfiguration Details:")
            print(f"  Google Drive Client ID: {'*' * 20}{config.google_drive.client_id[-8:] if config.google_drive.client_id else 'NOT SET'}")
            print(f"  Database Path: {config.database.db_path}")
            print(f"  Max Concurrent Files: {config.indexing.max_concurrent_files}")
            print(f"  Confidence Threshold: {config.query.confidence_threshold}")
            sys.exit(0)
    
    except Exception as e:
        print(f"\n✗ Failed to load configuration: {e}")
        sys.exit(1)
