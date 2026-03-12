# Abstraction Layers

This directory contains pluggable abstraction layers that enable easy switching between different service providers without changing application code.

## Architecture

The system uses three main abstraction layers:

1. **Vector Store** - For storing and searching embeddings
2. **Embedding Service** - For generating text embeddings
3. **LLM Service** - For natural language generation

Each abstraction follows the same pattern:
- Abstract base class defining the interface
- Multiple concrete implementations for different providers
- Factory class for instantiation based on configuration

## Vector Store Abstraction

### Supported Providers

- **ChromaDB** (MVP/Local) - Local vector database, perfect for development
- **OpenSearch** (Production) - Scalable cloud vector database

### Interface

```python
class VectorStore(ABC):
    def create_collection(name, dimension, metadata_schema) -> bool
    def add_embeddings(collection, ids, embeddings, documents, metadata) -> bool
    def search(collection, query_embedding, top_k, filters) -> List[Dict]
    def delete_by_id(collection, ids) -> bool
    def update_embeddings(collection, ids, embeddings, documents, metadata) -> bool
```

### Usage

```python
from src.abstractions import VectorStoreFactory

# Create from configuration
vector_store = VectorStoreFactory.create("chromadb", {
    "persist_directory": "./chroma_db"
})

# Or for OpenSearch
vector_store = VectorStoreFactory.create("opensearch", {
    "host": "localhost",
    "port": 9200,
    "username": "admin",
    "password": "admin"
})

# Use the same interface regardless of provider
vector_store.create_collection("my_collection", dimension=384, metadata_schema={})
vector_store.add_embeddings("my_collection", ids, embeddings, documents, metadata)
results = vector_store.search("my_collection", query_embedding, top_k=10)
```

## Embedding Service Abstraction

### Supported Providers

- **OpenAI** - High quality, API-based (text-embedding-3-small, text-embedding-3-large)
- **Sentence Transformers** - Free, local models (all-MiniLM-L6-v2, all-mpnet-base-v2)
- **Cohere** - API-based alternative (embed-english-v3.0)

### Interface

```python
class EmbeddingService(ABC):
    def get_embedding_dimension() -> int
    def embed_text(text) -> List[float]
    def embed_batch(texts) -> List[List[float]]
    def get_model_name() -> str
```

### Usage

```python
from src.abstractions import EmbeddingServiceFactory

# OpenAI
embedding_service = EmbeddingServiceFactory.create("openai", {
    "api_key": "sk-...",
    "model": "text-embedding-3-small"
})

# Sentence Transformers (local, free)
embedding_service = EmbeddingServiceFactory.create("sentence-transformers", {
    "model": "all-MiniLM-L6-v2"
})

# Use the same interface
embedding = embedding_service.embed_text("What is the revenue?")
embeddings = embedding_service.embed_batch(["text1", "text2", "text3"])
```

## LLM Service Abstraction

### Supported Providers

- **OpenAI** - GPT-4, GPT-3.5-turbo
- **Anthropic** - Claude 3.5 Sonnet, Claude 3 Opus
- **Google Gemini** - Gemini Pro

### Interface

```python
class LLMService(ABC):
    def generate(prompt, system_prompt, temperature, max_tokens) -> str
    def generate_structured(prompt, response_schema, system_prompt) -> Dict
    def get_model_name() -> str
```

### Usage

```python
from src.abstractions import LLMServiceFactory

# OpenAI
llm_service = LLMServiceFactory.create("openai", {
    "api_key": "sk-...",
    "model": "gpt-4"
})

# Anthropic Claude
llm_service = LLMServiceFactory.create("anthropic", {
    "api_key": "sk-ant-...",
    "model": "claude-3-5-sonnet-20241022"
})

# Use the same interface
answer = llm_service.generate(
    prompt="What is the total revenue?",
    system_prompt="You are a helpful assistant.",
    temperature=0.7,
    max_tokens=1000
)

# Structured output
result = llm_service.generate_structured(
    prompt="Extract entities from this query",
    response_schema={"entities": ["string"], "intent": "string"}
)
```

## Migration Guide

### Switching Vector Stores

To migrate from ChromaDB to OpenSearch:

1. Update `.env`:
   ```
   VECTOR_STORE_PROVIDER=opensearch
   OPENSEARCH_HOST=your-host
   OPENSEARCH_PORT=9200
   OPENSEARCH_USERNAME=admin
   OPENSEARCH_PASSWORD=your-password
   ```

2. Run migration script (optional):
   ```bash
   python scripts/migrate_vector_store.py --from chromadb --to opensearch
   ```

3. Restart application - no code changes needed!

### Switching Embedding Models

To switch from OpenAI to local Sentence Transformers:

1. Update `.env`:
   ```
   EMBEDDING_PROVIDER=sentence-transformers
   EMBEDDING_MODEL=all-MiniLM-L6-v2
   ```

2. Re-index data (embeddings will have different dimensions):
   ```bash
   python -m src.cli index full
   ```

3. Restart application

### Switching LLM Providers

To switch from OpenAI to Anthropic Claude:

1. Update `.env`:
   ```
   LLM_PROVIDER=anthropic
   LLM_API_KEY=sk-ant-...
   LLM_MODEL=claude-3-5-sonnet-20241022
   ```

2. Restart application - no code changes needed!

## Error Handling

All implementations include:
- Comprehensive error logging
- Retry logic with exponential backoff for API calls
- Rate limit handling
- Network error recovery
- Graceful degradation

## Testing

Run tests for abstraction layers:

```bash
# Test all abstractions
pytest tests/test_abstractions.py

# Test specific provider
pytest tests/test_abstractions.py::test_chromadb_store
pytest tests/test_abstractions.py::test_openai_embedding
pytest tests/test_abstractions.py::test_anthropic_llm
```

## Adding New Providers

To add a new provider:

1. Create implementation class inheriting from abstract base class
2. Implement all required methods
3. Add to factory class
4. Update configuration validation
5. Add tests
6. Update documentation

Example:

```python
# src/abstractions/pinecone_store.py
from .vector_store import VectorStore

class PineconeStore(VectorStore):
    def __init__(self, api_key: str, environment: str):
        # Initialize Pinecone client
        pass
    
    def create_collection(self, name, dimension, metadata_schema):
        # Implement method
        pass
    
    # ... implement other methods

# Update factory
# src/abstractions/vector_store_factory.py
class VectorStoreFactory:
    @staticmethod
    def create(store_type: str, config: Dict[str, Any]) -> VectorStore:
        if store_type == "pinecone":
            return PineconeStore(
                api_key=config["api_key"],
                environment=config["environment"]
            )
        # ... existing providers
```

## Performance Considerations

- **ChromaDB**: Best for < 1M vectors, local development
- **OpenSearch**: Scales to billions of vectors, production-ready
- **Sentence Transformers**: No API costs, slower than cloud APIs
- **OpenAI Embeddings**: Fast, high quality, API costs apply
- **GPT-4**: Highest quality, slower, higher cost
- **Claude 3.5 Sonnet**: Great balance of quality and speed
- **GPT-3.5-turbo**: Fast, cost-effective, good for development

## Configuration Best Practices

1. Use environment variables for all credentials
2. Never commit API keys to version control
3. Use different configurations for dev/staging/prod
4. Monitor API usage and costs
5. Set appropriate rate limits
6. Use local models for development when possible
7. Test migrations in staging before production
