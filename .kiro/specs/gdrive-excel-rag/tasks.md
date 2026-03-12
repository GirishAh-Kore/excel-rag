# Implementation Plan

This implementation plan breaks down the Google Drive Excel RAG system into incremental, actionable coding tasks. Each task builds on previous work and references specific requirements from the requirements document.

The system is designed with pluggable abstractions for vector stores, embedding models, and LLMs, allowing easy migration from MVP (ChromaDB + OpenAI) to production (OpenSearch + Claude/other models) without code changes.

## Implementation Status

### ✅ Completed (Tasks 1-7, 18)
- **Infrastructure**: Project structure, dependencies, configuration management
- **Abstraction Layers**: Vector stores, embedding services, LLM services, cache services
- **Multi-language Support**: Language detection, tokenization, normalization, preprocessing (Thai + English)
- **Data Models**: Domain models, database schema, migrations
- **Authentication**: OAuth 2.0 flow, token storage, token refresh
- **Google Drive Integration**: File listing, downloading, change detection, rate limiting
- **Content Extraction**: Excel parsing, formulas, pivot tables, charts, LLM summarization
- **Indexing Pipeline**: Full/incremental indexing, embedding generation, vector storage, metadata storage

### 🚧 In Progress (Tasks 8-17)
- **Query Processing**: Query analyzer, semantic search, conversation context, clarification
- **File/Sheet Selection**: Ranking algorithms, date parsing, preference learning
- **Comparison Engine**: Sheet alignment, difference calculation, result formatting
- **Answer Generation**: Prompts, data formatting, citations, confidence scoring
- **API Endpoints**: Authentication, indexing, query endpoints
- **CLI Interface**: Command updates for query and indexing
- **Logging & Monitoring**: Structured logging, correlation IDs, metrics
- **Testing**: Unit tests, integration tests, end-to-end tests

### 📋 Remaining Work
The remaining tasks focus on the query processing pipeline, API endpoints, CLI enhancements, and comprehensive testing. All foundational components (authentication, extraction, indexing) are complete and ready to use.

## Task List

- [x] 1. Set up project structure and core dependencies
  - Create Python project with virtual environment
  - Install core dependencies: FastAPI, openpyxl, google-api-python-client, chromadb, opensearch-py, openai, anthropic, sentence-transformers, cohere, python-dotenv
  - Create directory structure: src/abstractions, src/auth, src/gdrive, src/extraction, src/indexing, src/query, src/models, src/database, tests/
  - Set up configuration management with environment variables (.env file)
  - Create main application entry point with FastAPI app initialization
  - _Requirements: All (foundational)_

- [x] 2. Implement abstraction layers for pluggability
  - [x] 2.1 Create vector store abstraction layer
    - Define VectorStore abstract base class with interface methods (create_collection, add_embeddings, search, delete_by_id, update_embeddings)
    - Implement ChromaDBStore for MVP with all interface methods
    - Implement OpenSearchStore for production with all interface methods
    - Create VectorStoreFactory for instantiation based on configuration
    - Add comprehensive error handling and logging
    - _Requirements: 3.5_
  
  - [x] 2.2 Create embedding service abstraction layer
    - Define EmbeddingService abstract base class (get_embedding_dimension, embed_text, embed_batch, get_model_name)
    - Implement OpenAIEmbeddingService with support for text-embedding-3-small and text-embedding-3-large
    - Implement SentenceTransformerService for local embeddings
    - Implement CohereEmbeddingService
    - Create EmbeddingServiceFactory
    - Add rate limiting and retry logic for API-based services
    - _Requirements: 3.5_
  
  - [x] 2.3 Create LLM service abstraction layer
    - Define LLMService abstract base class (generate, generate_structured, get_model_name)
    - Implement OpenAILLMService with support for GPT-4 and GPT-3.5-turbo
    - Implement AnthropicLLMService with support for Claude Sonnet and Opus
    - Implement GeminiLLMService
    - Create LLMServiceFactory
    - Add streaming support
    - _Requirements: 4.1, 4.2, 7.1_
  
  - [x] 2.4 Create configuration management system
    - Define configuration dataclasses (VectorStoreConfig, EmbeddingConfig, LLMConfig, AppConfig)
    - Implement environment variable loading with validation
    - Add configuration validation with helpful error messages
    - Create .env.example file with all configuration options documented
    - Support multiple profiles (development, production)
    - _Requirements: All_
  
  - [x] 2.5 Implement multi-language support (Thai + English)
    - [x] 2.5.1 Create language detection module
      - Implement LanguageDetector class using langdetect and fasttext
      - Add detect() method for single language detection
      - Add detect_mixed() method for mixed-language content
      - Add confidence scoring for detection results
      - Handle edge cases (very short text, numbers only)
      - _Requirements: 11.1, 12.2_
    
    - [x] 2.5.2 Implement tokenization layer
      - Define Tokenizer abstract base class with tokenize() and detokenize() methods
      - Implement EnglishTokenizer using spaCy
      - Implement ThaiTokenizer using pythainlp (newmm algorithm)
      - Implement MultilingualTokenizer that delegates to language-specific tokenizers
      - Add TokenizerFactory for instantiation
      - Handle mixed-language tokenization
      - _Requirements: 11.2, 13.4_
    
    - [x] 2.5.3 Implement text normalization layer
      - Define TextNormalizer abstract base class with normalize(), lemmatize(), and stem() methods
      - Implement EnglishNormalizer with spaCy lemmatization for handling plurals, tenses, and morphological variations
      - Implement ThaiNormalizer with pythainlp for Thai-specific normalization
      - Add case normalization and whitespace handling
      - Create NormalizerFactory for instantiation
      - _Requirements: 13.1, 13.2, 13.3_
    
    - [x] 2.5.4 Create text preprocessing pipeline
      - Implement TextPreprocessor class that orchestrates detection, tokenization, and normalization
      - Add preprocess_for_embedding() method for preparing text before embedding generation
      - Add preprocess_for_matching() method for cell-level keyword matching
      - Add extract_keywords() method for search term extraction
      - Implement caching for preprocessing results
      - Add language-aware preprocessing strategies
      - _Requirements: 11.2, 12.1, 13.5_
    
    - [x] 2.5.5 Update configuration for multi-language support
      - Add language configuration to AppConfig (supported_languages, default_language)
      - Add text processing configuration (enable_lemmatization, thai_tokenizer_engine)
      - Add matching strategy configuration (semantic_threshold, enable_keyword_fallback)
      - Update .env.example with language settings
      - Add validation for language-related configuration
      - _Requirements: 11.1, 12.5_
    
    - [x] 2.5.6 Install and configure language processing dependencies
      - Install langdetect, fasttext for language detection
      - Install and download spaCy English model (en_core_web_sm)
      - Install pythainlp and download Thai language data
      - Install nltk and download required corpora
      - Install python-Levenshtein for fuzzy matching
      - Create dependency installation script
      - Add dependency checks to application startup
      - _Requirements: 11.2, 13.3_

- [x] 3. Implement data models and database schema
  - [x] 3.1 Create Pydantic models for core domain objects
    - Define FileMetadata, SheetData, WorkbookData, CellData models
    - Define PivotTableData and ChartData models
    - Define query-related models: QueryResult, RankedFile, SheetSelection, ComparisonResult, AlignedData
    - Add data type enums: FileStatus, DataType
    - Add validation rules and default values
    - _Requirements: 3.1, 3.2, 3.3, 8.1, 8.2_
  
  - [x] 3.2 Implement SQLite database schema and connection management
    - Create database initialization script with tables: files, sheets, pivot_tables, charts, user_preferences, query_history
    - Implement database connection pooling and context managers
    - Create database migration utilities for schema updates
    - Add indexes for frequently queried columns
    - _Requirements: 2.3, 5.5, 9.1_
  
  - [x] 3.3 Initialize vector store collections using abstraction
    - Use VectorStoreFactory to create vector store instance from configuration
    - Initialize three collections: excel_sheets, excel_pivots, excel_charts
    - Configure collection parameters based on embedding service dimension
    - Add collection existence checking and recreation logic
    - _Requirements: 3.5_

- [x] 4. Build authentication layer
  - [x] 4.1 Implement OAuth 2.0 flow for Google Drive
    - Create OAuth configuration with client ID and secret from environment
    - Implement authorization URL generation with appropriate scopes
    - Implement callback handler to exchange authorization code for tokens
    - Add state parameter for CSRF protection
    - _Requirements: 1.1, 1.2_
  
  - [x] 4.2 Implement secure token storage
    - Create encryption utilities using Fernet for token encryption
    - Implement file-based token storage with encryption
    - Create token retrieval and decryption methods
    - Store encryption key securely (environment variable)
    - _Requirements: 1.2_
  
  - [x] 4.3 Implement automatic token refresh
    - Create token expiration checking logic (5-minute buffer)
    - Implement automatic refresh token exchange
    - Handle refresh failures with re-authentication prompts
    - Add token refresh logging
    - _Requirements: 1.4_
  
  - [x] 4.4 Create authenticated Google Drive client factory
    - Implement method to create authenticated googleapiclient service
    - Add authentication status checking
    - Implement token revocation functionality
    - Handle authentication errors gracefully
    - _Requirements: 1.3, 1.5_

- [x] 5. Implement Google Drive connector
  - [x] 5.1 Create file listing functionality
    - Implement recursive folder traversal using Google Drive API
    - Filter for Excel file types (.xlsx, .xls, .xlsm)
    - Extract file metadata (ID, name, path, size, modified time, MD5)
    - Implement pagination handling (100 files per page)
    - Build full file paths from folder hierarchy
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 5.2 Implement file download functionality
    - Create method to download file content as bytes
    - Implement streaming for large files
    - Add error handling for inaccessible files
    - Add download progress tracking
    - _Requirements: 3.1, 10.1_
  
  - [x] 5.3 Implement rate limiting and retry logic
    - Create exponential backoff decorator (1s to 32s)
    - Handle 403 rate limit errors with retries
    - Handle network errors with retries (max 5 attempts)
    - Log all retry attempts with details
    - _Requirements: 10.3_
  
  - [x] 5.4 Implement change detection for incremental indexing
    - Create method to fetch changes using Google Drive Changes API
    - Store and manage page tokens for change tracking
    - Identify added, modified, and deleted files
    - Filter changes to only Excel files
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

- [x] 6. Build content extraction engine
  - [x] 6.1 Implement basic Excel file parsing
    - Create workbook loader using openpyxl for .xlsx files
    - Add xlrd support for legacy .xls files
    - Extract workbook-level metadata
    - Iterate through all sheets in workbook
    - Handle password-protected files gracefully
    - _Requirements: 3.1, 8.1_
  
  - [x] 6.2 Implement sheet data extraction
    - Detect header rows (analyze first 5 rows for text-heavy content)
    - Extract column headers and infer data types
    - Read cell values with data type preservation
    - Handle merged cells (associate value with all cells in range)
    - Limit processing to 10,000 rows per sheet
    - _Requirements: 3.2, 3.3, 8.1, 8.4_
  
  - [x] 6.3 Implement formula handling
    - Extract both formula text and calculated values using openpyxl
    - Detect and store formula errors (#DIV/0!, #REF!, #VALUE!, #N/A, etc.)
    - Handle cross-sheet references
    - Store formula metadata (is_formula flag, error type)
    - Handle GETPIVOTDATA formulas specially
    - _Requirements: 8.2_
  
  - [x] 6.4 Implement cell formatting extraction
    - Extract number formats (currency, percentage, date)
    - Store formatted string representations
    - Parse and normalize date values to ISO 8601
    - Handle custom number formats
    - _Requirements: 8.3, 8.5_
  
  - [x] 6.5 Implement pivot table extraction
    - Access pivot table definitions via worksheet._pivots
    - Extract row fields, column fields, data fields, and filters
    - Capture aggregation types and calculated results
    - Generate natural language descriptions of pivot tables
    - Handle pivot tables without source data gracefully
    - _Requirements: 3.3_
  
  - [x] 6.6 Implement chart extraction
    - Access chart objects via worksheet._charts
    - Extract chart type, title, and axis labels
    - Identify source data ranges for chart series
    - Generate natural language descriptions of charts
    - Handle charts with external data sources
    - _Requirements: 3.3_
  
  - [x] 6.7 Create embedding text generation
    - Generate multiple text chunks per sheet (headers, summary, columns)
    - Create descriptions for pivot tables with field names and aggregations
    - Create descriptions for charts with type and data context
    - Include file name, sheet name, and context in embeddings
    - Generate sample data summaries (first 5 rows)
    - _Requirements: 3.5_
  
  - [x] 6.8 Implement error handling for corrupted files
    - Wrap extraction in try-except blocks
    - Log specific error types (corrupted, unsupported format, memory errors)
    - Skip problematic files and continue processing
    - Return partial results when possible
    - Track failed files for reporting
    - _Requirements: 10.1, 10.2_

- [x] 7. Build indexing pipeline
  - [x] 7.1 Create indexing orchestrator
    - Implement full indexing workflow (list files → extract → embed → store)
    - Implement incremental indexing (only changed files based on MD5)
    - Add parallel processing for files (max 5 concurrent workers using ThreadPoolExecutor)
    - Track indexing state in SQLite (files processed, pending, failed)
    - Add pause/resume functionality
    - _Requirements: 2.4, 9.2_
  
  - [x] 7.2 Implement embedding generation
    - Use EmbeddingService abstraction (supports multiple providers)
    - Batch embedding requests (100 texts per batch)
    - Handle API errors and rate limits with retries
    - Cache embeddings to avoid regeneration for unchanged content
    - Track embedding costs (for API-based services)
    - _Requirements: 3.5_
  
  - [x] 7.3 Implement vector database storage
    - Use VectorStore abstraction for storage
    - Store sheet embeddings in excel_sheets collection
    - Store pivot table embeddings in excel_pivots collection
    - Store chart embeddings in excel_charts collection
    - Include rich metadata for filtering (dates, file names, data types, pivot/chart flags)
    - Handle duplicate IDs gracefully (update instead of insert)
    - _Requirements: 3.5_
  
  - [x] 7.4 Implement metadata database storage
    - Insert file records into files table with all metadata
    - Insert sheet records into sheets table with structure info
    - Insert pivot table records into pivot_tables table
    - Insert chart records into charts table
    - Use MD5 checksums to detect changes
    - Update existing records instead of duplicating
    - _Requirements: 2.3, 9.1_
  
  - [x] 7.5 Create indexing progress tracking and reporting
    - Track files processed, failed, and skipped in real-time
    - Calculate and display progress percentage
    - Generate IndexingReport with summary statistics
    - Log detailed information for debugging
    - Estimate time remaining based on current throughput
    - _Requirements: 2.5_

- [x] 8. Implement query processing engine
  - [x] 8.1 Create query analyzer module
    - Create QueryAnalyzer class in src/query/query_analyzer.py
    - Use LLMService abstraction to extract entities, dates, and intent from queries
    - Detect comparison keywords (compare, difference, vs, between, change from)
    - Identify data types being requested (numbers, dates, text, formulas)
    - Parse temporal references (last month, Q1, January, 2024) using dateparser
    - Extract file name hints and path patterns from query
    - Return structured QueryAnalysis with entities, intent, temporal_refs, comparison_type
    - _Requirements: 4.2_
  
  - [x] 8.2 Implement semantic search module
    - Create SemanticSearcher class in src/query/semantic_searcher.py
    - Use EmbeddingService to generate query embedding
    - Search excel_sheets collection with cosine similarity using VectorStorageManager
    - Search excel_pivots and excel_charts collections when relevant (detect from query)
    - Apply metadata filters (dates, file names, data types, has_pivot_tables, has_charts)
    - Retrieve top 10 candidate sheets (or top 5 files for comparisons)
    - Return SearchResults with ranked candidates and scores
    - _Requirements: 3.5, 5.1_
  
  - [x] 8.3 Create conversation context management
    - Create ConversationManager class in src/query/conversation_manager.py
    - Store previous queries and selected files in session using CacheService abstraction
    - Use context to resolve ambiguous references (follow-up questions like "what about last month?")
    - Maintain session state across multiple queries with session IDs
    - Implement session timeout (30 minutes) using cache TTL
    - Provide methods to get_context(), update_context(), clear_context()
    - _Requirements: 4.5_
  
  - [x] 8.4 Implement clarification question generation
    - Create ClarificationGenerator class in src/query/clarification_generator.py
    - Detect ambiguous queries (low confidence < 70%, multiple candidates with similar scores)
    - Use LLMService to generate clarifying questions based on candidates
    - Present options to user when confidence < 70% (top 3 candidates)
    - Handle user responses to clarifications and update context
    - Return ClarificationRequest with questions and options
    - _Requirements: 4.4_
  
  - [x] 8.5 Create main query engine orchestrator
    - Create QueryEngine class in src/query/query_engine.py
    - Orchestrate query processing pipeline: analyze → search → select → retrieve → answer
    - Integrate QueryAnalyzer, SemanticSearcher, ConversationManager, ClarificationGenerator
    - Coordinate with FileSelector, SheetSelector, and AnswerGenerator
    - Handle comparison queries by routing to ComparisonEngine
    - Return QueryResult with answer, sources, confidence, and clarification if needed
    - Add comprehensive error handling and logging
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 9. Build file and sheet selection logic
  - [x] 9.1 Implement file ranking algorithm
    - Create FileSelector class in src/query/file_selector.py
    - Calculate semantic similarity score from vector search results (50% weight)
    - Calculate metadata match score (30% weight) - dates, paths, recency
    - Calculate user preference score (20% weight) from history using MetadataStorageManager
    - Combine scores into final ranking with normalization (0-1 scale)
    - Sort files by final score descending
    - Return RankedFile list with detailed scoring breakdown
    - _Requirements: 5.1, 5.2_
  
  - [x] 9.2 Implement date parsing from file names
    - Create DateParser utility class in src/query/date_parser.py
    - Create regex patterns for common date formats (YYYY-MM-DD, MM-DD-YYYY, Month YYYY, Q1 2024, etc.)
    - Extract dates from file names and paths using pattern matching
    - Match extracted dates against query temporal references from QueryAnalysis
    - Handle relative dates (last month, this year, yesterday) using dateparser library
    - Return ParsedDate with confidence score and matched format
    - _Requirements: 5.3_
  
  - [x] 9.3 Implement user preference learning
    - Create PreferenceManager class in src/query/preference_manager.py
    - Store user file selections in user_preferences table with query pattern
    - Query historical preferences for similar queries using fuzzy matching (Levenshtein distance)
    - Apply preference boost to ranking scores (exponential decay based on age)
    - Decay old preferences over time (reduce weight after 30 days)
    - Provide methods to record_preference(), get_preferences(), clear_old_preferences()
    - _Requirements: 5.5_
  
  - [x] 9.4 Create file selection decision logic
    - Add select_file() method to FileSelector class
    - Select top file automatically if confidence > 90%
    - Present top 3 files with scores if confidence < 90%
    - Handle user confirmation and update preferences via PreferenceManager
    - Support "none of these" option to trigger broader search
    - Return FileSelection with selected file or clarification request
    - _Requirements: 5.4_
  
  - [x] 9.5 Implement sheet selection algorithm
    - Create SheetSelector class in src/query/sheet_selector.py
    - Calculate sheet name similarity to query (30% weight) using fuzzy matching (fuzzywuzzy)
    - Calculate header/column match score (40% weight) using keyword matching
    - Calculate data type alignment score (20% weight) based on query intent
    - Calculate content sample similarity (10% weight) using embeddings from search results
    - Select sheet with highest score > 70%
    - Return SheetSelection with selected sheet and relevance score
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 9.6 Handle multi-sheet scenarios
    - Add select_multiple_sheets() method to SheetSelector class
    - Process all sheets in parallel using ThreadPoolExecutor (max 5 workers)
    - Examine multiple sheets if scores > 70%
    - Combine data from multiple sheets when appropriate (union or join)
    - Indicate which sheets were used in response metadata
    - Return MultiSheetSelection with list of selected sheets and combination strategy
    - _Requirements: 6.4_

- [x] 10. Implement comparison engine
  - [x] 10.1 Create file comparison orchestrator
    - Create ComparisonEngine class in src/query/comparison_engine.py
    - Detect comparison queries using QueryAnalyzer results (is_comparison flag)
    - Retrieve multiple relevant files (up to 5) using SemanticSearcher with comparison mode
    - Coordinate alignment and analysis workflow: align → calculate → format
    - Handle cases where files have different structures (missing columns, different row counts)
    - Return ComparisonResult with aligned data, differences, and summary
    - _Requirements: 4.2_
  
  - [x] 10.2 Implement sheet alignment algorithm
    - Create SheetAligner class in src/query/sheet_aligner.py
    - Match sheets by name using fuzzy matching (Levenshtein distance < 3, threshold 0.8)
    - Identify common columns by header matching (exact and fuzzy with threshold 0.85)
    - Find key columns for row alignment (dates, IDs, categories) using heuristics
    - Handle missing columns and structural differences gracefully (mark as gaps)
    - Create AlignedData structure with column mappings and row alignments
    - Return alignment quality score and warnings for structural differences
    - _Requirements: 5.1, 5.2_
  
  - [x] 10.3 Create difference calculation engine
    - Create DifferenceCalculator class in src/query/difference_calculator.py
    - Calculate absolute differences (value2 - value1) for numerical columns
    - Calculate percentage changes with division-by-zero handling (return None or "N/A")
    - Detect trends (increasing, decreasing, stable) with configurable thresholds (±5%)
    - Compute aggregates across files (sum, average, min, max, count) for numerical data
    - Handle missing data points (mark as "missing" in results)
    - Return DifferenceResult with calculations and trend analysis
    - _Requirements: 5.1, 5.2_
  
  - [x] 10.4 Implement comparison result formatting
    - Create ComparisonFormatter class in src/query/comparison_formatter.py
    - Generate comparison summary with key findings using LLMService
    - Create structured data for visualization (comparison tables, trend data)
    - Cite sources for all compared values (file name, sheet name, cell range)
    - Cache aligned data for follow-up questions using CacheService (5-minute TTL)
    - Format output as natural language with embedded data tables
    - Return formatted ComparisonResult ready for presentation
    - _Requirements: 7.1, 7.2_

- [x] 11. Build answer generation system
  - [x] 11.1 Create answer generation prompts
    - Create PromptBuilder class in src/query/prompt_builder.py
    - Design structured prompts for LLMService with clear instructions and context
    - Include query, retrieved data, and formatting guidelines in prompts
    - Add examples for different answer types (single value, table, comparison, formula)
    - Create separate prompt templates for formula explanations
    - Support multi-language prompts (English and Thai) based on query language
    - Return formatted prompt ready for LLM generation
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [x] 11.2 Implement data formatting utilities
    - Create DataFormatter class in src/query/data_formatter.py
    - Format numbers with original Excel formatting (currency, percentage, thousands separator)
    - Format dates in readable format (e.g., "January 15, 2024") using dateutil
    - Handle currency symbols and percentage formatting
    - Create readable tables for multi-row data (markdown format with alignment)
    - Format formulas with explanations
    - Support Thai number and date formatting
    - _Requirements: 7.2, 7.3_
  
  - [x] 11.3 Implement source citation generation
    - Create CitationGenerator class in src/query/citation_generator.py
    - Include file name, sheet name, and cell range in citations
    - Format citations consistently (e.g., "Source: Expenses_Jan2024.xlsx, Sheet: Summary, Cell: B10")
    - Link citations to specific data points in answer using footnote-style references
    - Support multiple sources in single answer with numbered citations
    - Generate citation list at end of answer
    - _Requirements: 7.1_
  
  - [x] 11.4 Create confidence scoring
    - Create ConfidenceScorer class in src/query/confidence_scorer.py
    - Calculate confidence based on data completeness (all requested data found: 40%)
    - Factor in semantic similarity scores from vector search (30%)
    - Consider ambiguity in query and results (20%)
    - Factor in file/sheet selection confidence (10%)
    - Return confidence score (0-100) with answer
    - Provide confidence explanation with breakdown
    - _Requirements: 7.4_
  
  - [x] 11.5 Implement "no results" handling
    - Create NoResultsHandler class in src/query/no_results_handler.py
    - Detect when no relevant data is found (empty search results or low confidence)
    - Generate helpful error messages explaining what was searched
    - Suggest query refinements based on indexed data (available files, sheets, columns)
    - Offer to search with relaxed criteria (lower threshold, broader filters)
    - Return NoResultsResponse with suggestions and alternatives
    - _Requirements: 7.5_
  
  - [x] 11.6 Create main answer generator
    - Create AnswerGenerator class in src/query/answer_generator.py
    - Integrate PromptBuilder, DataFormatter, CitationGenerator, ConfidenceScorer
    - Orchestrate answer generation: format data → build prompt → generate → add citations
    - Use LLMService abstraction for answer generation
    - Handle different answer types (direct answer, table, comparison, formula explanation)
    - Add error handling for LLM failures (fallback to structured data)
    - Return QueryResult with formatted answer, sources, and confidence
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 12. Create API endpoints
  - [x] 12.0 Set up API directory structure
    - Create src/api/ directory
    - Create src/api/__init__.py
    - Create src/api/models.py for request/response models
    - Create src/api/middleware.py for middleware components
    - Create src/api/dependencies.py for dependency injection
    - _Requirements: All API endpoints_
  
  - [x] 12.1 Implement authentication endpoints
    - Create auth router in src/api/auth.py
    - POST /auth/login - Initiate OAuth flow, return authorization URL
    - GET /auth/callback - Handle OAuth callback with code parameter and state validation
    - POST /auth/logout - Revoke access and clear tokens
    - GET /auth/status - Check authentication status and token expiry
    - Add proper error responses and status codes (401, 403, 500)
    - Create Pydantic models for request/response validation
    - _Requirements: 1.1, 1.2, 1.5_
  
  - [x] 12.2 Implement indexing endpoints
    - Create indexing router in src/api/indexing.py
    - POST /index/full - Trigger full indexing, return job ID and initial status
    - POST /index/incremental - Trigger incremental indexing with optional file filters
    - GET /index/status/{job_id} - Get indexing progress with percentage and current file
    - GET /index/report/{job_id} - Get indexing summary report with statistics
    - POST /index/pause/{job_id} - Pause ongoing indexing
    - POST /index/resume/{job_id} - Resume paused indexing
    - POST /index/stop/{job_id} - Stop indexing
    - Add WebSocket endpoint /ws/index/{job_id} for real-time progress updates
    - _Requirements: 2.1, 2.5, 9.2, 9.5_
  
  - [x] 12.3 Implement query endpoints
    - Create query router in src/api/query.py
    - POST /query - Submit natural language query, return answer with sources and confidence
    - POST /query/clarify - Respond to clarification questions with user selection
    - GET /query/history - Retrieve query history with pagination (limit, offset)
    - DELETE /query/history - Clear query history for current session
    - GET /query/session/{session_id} - Get session context and history
    - POST /query/feedback - Submit feedback on query results for preference learning
    - _Requirements: 4.1, 4.4_
  
  - [x] 12.4 Add request validation and error handling
    - Create request/response models in src/api/models.py
    - Validate request bodies with Pydantic models (QueryRequest, IndexRequest, etc.)
    - Return structured error responses using ErrorResponse model
    - Implement global exception handlers for common errors (AuthError, NotFoundError, etc.)
    - Log all API requests and errors with correlation IDs using middleware
    - Add rate limiting per endpoint using slowapi (10 req/min for queries, 1 req/min for indexing)
    - Add request/response logging middleware
    - _Requirements: 10.5_
  
  - [x] 12.5 Integrate routers with main application
    - Update src/main.py to include all routers
    - Add router for auth endpoints with /auth prefix
    - Add router for indexing endpoints with /index prefix
    - Add router for query endpoints with /query prefix
    - Configure CORS for production deployment
    - Add API versioning (/api/v1 prefix)
    - Update health check to include component status

- [x] 13. Implement CLI interface
  - [x] 13.1 Update CLI commands for authentication
    - Update src/cli.py auth commands to use AuthenticationService
    - Command: auth login - Opens browser for OAuth using webbrowser module
    - Command: auth logout - Revokes tokens and clears storage
    - Command: auth status - Shows authentication status, token expiry, and user info
    - Add error handling and user-friendly messages
    - _Requirements: 1.1, 1.5_
  
  - [x] 13.2 Update CLI commands for indexing
    - Update src/cli.py index commands to use IndexingPipeline
    - Command: index full - Starts full indexing with progress bar
    - Command: index incremental - Starts incremental indexing
    - Command: index status - Shows current indexing status and progress
    - Command: index report - Shows detailed indexing report with statistics
    - Display progress bars using tqdm or rich
    - Display summary statistics on completion (files, sheets, costs)
    - Add --watch flag for continuous progress monitoring
    - _Requirements: 2.1, 2.5, 9.2_
  
  - [x] 13.3 Update CLI commands for querying
    - Update src/cli.py query commands to use QueryEngine
    - Command: query ask "question text" - Submits query and displays answer
    - Display formatted answers with citations using rich formatting
    - Handle clarification questions interactively with numbered options
    - Support follow-up questions in same session (maintain session ID)
    - Command: query history - Show recent queries and answers
    - Command: query clear - Clear query history
    - Add --session flag to specify session ID
    - _Requirements: 4.1, 7.1_
  
  - [x] 13.4 CLI commands for configuration already implemented
    - Commands already exist: config show, config set, config validate
    - No changes needed
    - _Requirements: All_

- [ ] 14. Add logging and monitoring
  - [x] 14.1 Set up structured logging
    - Create logging configuration in src/utils/logging_config.py
    - Configure JSON logging format with timestamp, level, message, context using python-json-logger
    - Set up log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) based on environment
    - Create separate log files for API, indexing, queries, errors in logs/ directory
    - Implement log rotation (daily, keep 30 days) using RotatingFileHandler
    - Add log filtering by component using logger names
    - Update all modules to use configured logger
    - _Requirements: 10.1, 10.2_
  
  - [x] 14.2 Add correlation IDs for request tracing
    - Create correlation ID middleware in src/api/middleware.py
    - Generate unique ID for each request using UUID4
    - Include correlation ID in all log entries via contextvars
    - Pass correlation ID through all components (add to function signatures where needed)
    - Return correlation ID in API responses (X-Correlation-ID header)
    - Add correlation ID to error responses for debugging
    - _Requirements: 10.5_
  
  - [x] 14.3 Implement performance metrics collection
    - Create metrics collector in src/utils/metrics.py
    - Track indexing throughput (files per minute) in IndexingOrchestrator
    - Track query response times (p50, p95, p99) using histogram
    - Track API latencies (Google Drive, embedding service, LLM, vector DB) with timers
    - Log memory usage during indexing using psutil
    - Create metrics endpoint GET /metrics for monitoring (Prometheus format)
    - Add metrics dashboard data endpoint GET /metrics/dashboard
    - _Requirements: 4.3, 9.5_

- [ ] 15. Configuration and deployment setup (mostly complete)
  - [x] 15.1 Configuration management already implemented
    - Configuration system already complete in src/config.py
    - .env.example files already created with documentation
    - Validation already implemented
    - Configuration profiles already supported
    - _Requirements: All_
  
  - [x] 15.2 Requirements files already created
    - requirements.txt already exists with dependencies
    - requirements-language.txt for language processing
    - setup.py already exists
    - Dependencies already documented
    - _Requirements: All_
  
  - [x] 15.3 README already created
    - README.md already exists with setup instructions
    - Authentication setup documented
    - Usage examples provided
    - Configuration options documented
    - _Requirements: All_
  
  - [x] 15.4 Create migration script for vector store switching
    - Create migration script in scripts/migrate_vector_store.py
    - Script to export data from ChromaDB (read all collections)
    - Script to import data into OpenSearch (create indices and bulk insert)
    - Validate data integrity after migration (count check, sample verification)
    - Document migration process in docs/MIGRATION.md
    - Add rollback capability in case of failure
    - _Requirements: 3.5_

- [x] 16. Write tests for core functionality
  - [ ]* 16.1 Create unit tests for query processing components
    - Create tests/test_query_analyzer.py for QueryAnalyzer
    - Create tests/test_semantic_searcher.py for SemanticSearcher
    - Create tests/test_file_selector.py for FileSelector
    - Create tests/test_sheet_selector.py for SheetSelector
    - Test with mock LLM and embedding services
    - _Requirements: 4.2, 5.1, 6.1_
  
  - [ ]* 16.2 Create unit tests for comparison engine
    - Create tests/test_comparison_engine.py for ComparisonEngine
    - Create tests/test_sheet_aligner.py for SheetAligner
    - Create tests/test_difference_calculator.py for DifferenceCalculator
    - Test with sample aligned data
    - Test edge cases (missing columns, different structures)
    - _Requirements: 5.1, 5.2_
  
  - [ ]* 16.3 Create unit tests for answer generation
    - Create tests/test_answer_generator.py for AnswerGenerator
    - Create tests/test_data_formatter.py for DataFormatter
    - Create tests/test_confidence_scorer.py for ConfidenceScorer
    - Test with mock LLM responses
    - Test different answer types (single value, table, comparison)
    - _Requirements: 7.1, 7.2, 7.4_
  
  - [ ]* 16.4 Create integration tests for query engine
    - Create tests/test_query_engine_integration.py
    - Test end-to-end query processing with sample indexed data
    - Test clarification flow
    - Test comparison queries
    - Test follow-up questions with context
    - _Requirements: 4.1, 4.2, 4.4, 4.5_
  
  - [ ]* 16.5 Create API endpoint tests
    - Create tests/test_api_auth.py for authentication endpoints
    - Create tests/test_api_indexing.py for indexing endpoints
    - Create tests/test_api_query.py for query endpoints
    - Use FastAPI TestClient for endpoint testing
    - Test request validation and error handling
    - _Requirements: All API endpoints_

- [ ]* 17. Integration and end-to-end testing
  - [ ]* 17.1 Set up test Google Drive account with sample files
    - Create diverse Excel files (various structures, formulas, pivots, charts)
    - Organize files in folders with different naming patterns
    - Include files with similar names and dates for disambiguation testing
    - Create files for comparison testing (monthly reports, regional data)
    - Document test data setup in tests/TEST_DATA.md
    - _Requirements: All_
  
  - [ ]* 17.2 Test complete user workflows
    - Create tests/test_e2e_workflows.py for end-to-end testing
    - Test: First-time authentication → Full indexing → Query
    - Test: Incremental indexing after file changes
    - Test: File disambiguation with similar files
    - Test: Cross-file comparison queries
    - Test: Follow-up questions with context
    - Test: Pivot table and chart queries
    - Test: Multi-language queries (English and Thai)
    - _Requirements: All_
  
  - [ ]* 17.3 Verify error handling and recovery
    - Create tests/test_error_handling.py
    - Test expired token handling and automatic refresh
    - Test rate limit handling with exponential backoff
    - Test corrupted file handling
    - Test network error recovery
    - Test partial indexing failures
    - Test LLM API failures and fallbacks
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [ ]* 17.4 Test provider switching
    - Create tests/test_provider_switching.py
    - Test switching from ChromaDB to OpenSearch
    - Test switching from OpenAI to Claude
    - Test switching embedding models
    - Verify no data loss during migration
    - Test configuration validation for different providers
    - _Requirements: All abstraction layers_

- [x] 18. Extraction enhancements (LLM summarization & configurable strategies)
  - [x] 18.1 Implement LLM-based sheet summarization
    - Create SheetSummarizer class for generating semantic summaries
    - Add generate_sheet_summary() method using LLM service abstractions
    - Implement rank_sheets_for_query() for query-based sheet ranking
    - Add llm_summary and summary_generated_at fields to SheetData model
    - Integrate with ConfigurableExtractor for automatic summary generation
    - _Requirements: 4.4 (disambiguation), 5.1 (sheet selection)_
  
  - [x] 18.2 Create configurable extraction architecture
    - Define ExtractionStrategy enum (openpyxl, gemini, llamaparse, auto)
    - Create ExtractionConfig model for extraction configuration
    - Implement ConfigurableExtractor with strategy pattern
    - Add quality evaluation metrics (ExtractionQuality model)
    - Implement smart extraction with automatic fallback
    - _Requirements: 3.1 (extraction), 10.1 (error handling)_
  
  - [x] 18.3 Add extraction strategy placeholders
    - Create GeminiExcelExtractor placeholder for Google Gemini integration
    - Create LlamaParseExtractor placeholder for LlamaParse integration
    - Document requirements for future implementation
    - Add configuration support for optional extractors
    - _Requirements: 3.1 (extensibility)_
  
  - [ ] 18.4 Update configuration for extraction enhancements
    - ExtractionConfig already added to AppConfig ✅
    - Environment variables already added to config.py ✅
    - Need to document in .env.example files:
      - ENABLE_LLM_SUMMARIZATION (default: true)
      - SUMMARIZATION_PROVIDER (default: openai)
      - SUMMARIZATION_MODEL (optional)
      - SUMMARIZATION_MAX_TOKENS (default: 150)
      - ENABLE_GEMINI_EXTRACTION (default: false)
      - GEMINI_API_KEY (optional)
      - GEMINI_MODEL (default: gemini-1.5-flash)
      - GEMINI_FALLBACK_ON_ERROR (default: true)
      - ENABLE_LLAMAPARSE (default: false)
      - LLAMAPARSE_API_KEY (optional)
      - USE_AUTO_EXTRACTION_STRATEGY (default: false)
      - EXTRACTION_COMPLEXITY_THRESHOLD (default: 0.7)
    - _Requirements: All (configuration)_
  
  - [x] 18.5 Create documentation and examples
    - Create EXTRACTION_ENHANCEMENTS.md with detailed documentation
    - Create ENHANCEMENT_SUMMARY.md with quick reference
    - Create configurable_extraction_usage.py example script
    - Document cost analysis for LLM summarization
    - Document migration guide for existing code
    - _Requirements: All (documentation)_

- [ ]* 19. Documentation and final polish
  - [ ]* 19.1 Create API documentation
    - Document all endpoints with request/response examples
    - Create OpenAPI/Swagger specification
    - Add authentication requirements
    - Document error codes and responses
    - _Requirements: All_
  
  - [ ]* 19.2 Create user guide
    - Write step-by-step usage guide
    - Add example queries and expected outputs
    - Document limitations and known issues
    - Add FAQ section
    - _Requirements: All_
  
  - [ ]* 19.3 Add inline code documentation
    - Add docstrings to all classes and methods
    - Add type hints throughout codebase
    - Add comments for complex logic
    - Generate API documentation from docstrings
    - _Requirements: All_
  
  - [ ]* 19.4 Create architecture documentation
    - Document abstraction layer design and benefits
    - Document migration paths between providers
    - Create architecture diagrams
    - Document design decisions and trade-offs
    - _Requirements: All_

- [x] 20. Build web application frontend
  - [x] 20.1 Set up React project structure
    - Initialize React app with TypeScript using Vite or Create React App
    - Install dependencies: React Router, Axios, Material-UI/Tailwind CSS
    - Set up project folder structure (components, pages, services, hooks)
    - Configure TypeScript and ESLint
    - Create basic App.tsx with routing setup
    - _Requirements: 14.1_
  
  - [x] 20.2 Implement authentication UI
    - Create LoginPage.tsx with username/password form
    - Create LoginForm.tsx component with validation
    - Implement authService.ts for API calls (login, logout, status)
    - Create useAuth.ts hook for authentication state management
    - Implement ProtectedRoute.tsx component for route protection
    - Store JWT token in localStorage or httpOnly cookie
    - Add error handling and display for failed login
    - _Requirements: 15.1, 15.2, 15.3, 15.4_
  
  - [x] 20.3 Build configuration page UI
    - Create ConfigPage.tsx with tabs for GDrive and File Upload
    - Create GDriveConnection.tsx component with connect/disconnect buttons
    - Display connection status and connected account email
    - Create FileUpload.tsx component with drag-and-drop zone
    - Implement file browser button and multiple file selection
    - Add upload progress bars for each file
    - Create IndexedFilesList.tsx component with table display
    - Add search, filter, and pagination to file list
    - Implement re-index and delete actions for files
    - _Requirements: 14.2, 16.1, 16.2, 16.3, 16.4, 16.5_
  
  - [x] 20.4 Build chat interface UI
    - Create ChatPage.tsx with sidebar and main chat area
    - Create ConversationSidebar.tsx for conversation history
    - Create ChatInterface.tsx for active chat display
    - Create MessageList.tsx to display messages
    - Create MessageItem.tsx for individual message rendering
    - Create QueryInput.tsx with multi-line text input and send button
    - Display source citations as expandable sections
    - Show confidence scores with badges
    - Add loading indicator during query processing
    - Implement new conversation and delete conversation features
    - _Requirements: 14.3, 14.4, 14.5, 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [x] 20.5 Implement frontend services and API integration
    - Create api.ts utility with Axios instance and interceptors
    - Implement fileService.ts for file upload, list, delete, reindex
    - Implement chatService.ts for query submission and session management
    - Add request/response interceptors for authentication tokens
    - Implement error handling and retry logic
    - Add loading states and error messages in UI
    - _Requirements: 14.1, 14.2, 14.3_
  
  - [x] 20.6 Add responsive design and styling
    - Implement responsive layouts for mobile, tablet, desktop
    - Style all components with Material-UI or Tailwind CSS
    - Add loading spinners and skeleton screens
    - Implement toast notifications for success/error messages
    - Add dark mode support (optional)
    - Ensure accessibility (ARIA labels, keyboard navigation)
    - _Requirements: 14.1_

- [x] 21. Implement web application backend endpoints
  - [x] 21.1 Create authentication endpoints
    - Implement POST /api/auth/login endpoint with hardcoded credentials
    - Generate JWT tokens on successful login
    - Implement POST /api/auth/logout endpoint
    - Implement GET /api/auth/status endpoint
    - Create authentication middleware for protected routes
    - Add session management and token validation
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 21.2 Create file management endpoints
    - Implement POST /api/files/upload endpoint with multipart form data
    - Add file validation (type, size) and save to upload directory
    - Trigger indexing pipeline for uploaded files
    - Implement GET /api/files/list endpoint with pagination
    - Implement DELETE /api/files/{file_id} endpoint
    - Implement POST /api/files/{file_id}/reindex endpoint
    - Implement GET /api/files/indexing-status endpoint
    - _Requirements: 16.3, 16.4, 16.5_
  
  - [x] 21.3 Create Google Drive configuration endpoints
    - Implement POST /api/config/gdrive/connect to initiate OAuth
    - Implement GET /api/config/gdrive/callback for OAuth callback
    - Implement DELETE /api/config/gdrive/disconnect to revoke access
    - Implement GET /api/config/gdrive/status to check connection
    - Store OAuth tokens securely per user session
    - _Requirements: 16.1, 16.2_
  
  - [x] 21.4 Create chat session endpoints
    - Implement POST /api/chat/query endpoint for query submission
    - Integrate with existing QueryEngine for processing
    - Implement GET /api/chat/sessions endpoint to list sessions
    - Implement POST /api/chat/sessions to create new session
    - Implement DELETE /api/chat/sessions/{session_id} endpoint
    - Implement GET /api/chat/sessions/{session_id}/history endpoint
    - Store conversation history in database
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [x] 21.5 Add static file serving for frontend
    - Configure FastAPI to serve React build files
    - Set up static file routes for frontend assets
    - Implement catch-all route to serve index.html for client-side routing
    - Add CORS configuration for development
    - _Requirements: 14.1_

- [x] 22. Create Docker containerization
  - [x] 22.1 Create Dockerfile for application
    - Write multi-stage Dockerfile (frontend build, backend dependencies, final image)
    - Install system dependencies (curl, language processing libraries)
    - Copy application code and frontend build
    - Create necessary directories (/app/data, /app/uploads, /app/logs)
    - Set environment variables and expose port 8000
    - Add health check command
    - Configure Gunicorn with Uvicorn workers as entry point
    - _Requirements: 18.1, 18.2, 18.3, 18.4_
  
  - [x] 22.2 Create docker-compose.yml configuration
    - Define web service with build context and environment variables
    - Define ChromaDB service with persistent volume
    - Configure service dependencies and health checks
    - Set up named volumes for app-data, uploads, logs, chroma-data
    - Configure bridge network for service communication
    - Add restart policies (unless-stopped)
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_
  
  - [x] 22.3 Create environment configuration files
    - Create .env.example with all required environment variables
    - Document each environment variable with comments
    - Include settings for authentication, Google Drive, OpenAI, vector store
    - Add file upload and language processing settings
    - Create separate .env.production example for production deployment
    - _Requirements: 18.5_
  
  - [x] 22.4 Add Docker documentation and scripts
    - Create DOCKER.md with deployment instructions
    - Document local development setup with Docker
    - Document production deployment steps
    - Add useful Docker commands (start, stop, logs, backup, restore)
    - Create backup and restore scripts for volumes
    - Document monitoring and health check procedures
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [x] 22.5 Test Docker deployment
    - Build Docker images and verify no errors
    - Start services with docker-compose up
    - Verify web application is accessible on port 8000
    - Test authentication and file upload through web UI
    - Test chat functionality end-to-end
    - Verify data persistence across container restarts
    - Test backup and restore procedures
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 19.1, 19.2, 19.3, 19.4, 19.5_

- [-] 23. Integration and testing for web application
  - [x] 23.1 Test authentication flow
    - Test login with correct credentials
    - Test login with incorrect credentials
    - Test session persistence across page refreshes
    - Test logout functionality
    - Test protected route access without authentication
    - _Requirements: 15.1, 15.2, 15.3, 15.4_
  
  - [x] 23.2 Test file upload and management
    - Test single file upload with progress tracking
    - Test multiple file upload
    - Test file type validation (accept only .xlsx, .xls, .xlsm)
    - Test file size validation
    - Test file list display with pagination
    - Test file deletion
    - Test file re-indexing
    - _Requirements: 16.3, 16.4, 16.5_
  
  - [ ] 23.3 Test Google Drive integration
    - Test OAuth connection flow
    - Test connection status display
    - Test file indexing from Google Drive
    - Test disconnection and token revocation
    - _Requirements: 16.1, 16.2_
  
  - [ ] 23.4 Test chat functionality
    - Test query submission and response display
    - Test source citations display
    - Test confidence score display
    - Test conversation history
    - Test new conversation creation
    - Test conversation deletion
    - Test follow-up questions with context
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [ ] 23.5 Test Docker deployment
    - Test building Docker images
    - Test starting services with docker-compose
    - Test accessing web application from browser
    - Test data persistence across container restarts
    - Test environment variable configuration
    - Test health checks and monitoring
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 19.1, 19.2, 19.3, 19.4, 19.5_
