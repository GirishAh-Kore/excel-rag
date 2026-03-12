# Implementation Plan: Excel Query Pipeline

## Overview

This implementation plan breaks down the Chunk Visibility & Smart Excel Query Pipeline feature into logical phases. The system uses Python with openpyxl for extraction, BGE-M3 for embeddings, ChromaDB for vector storage, and Ollama for LLM. All components follow SOLID principles with dependency injection and registry patterns.

## Tasks

- [x] 1. Foundation: Exception Hierarchy and Data Models
  - [x] 1.1 Create extended exception hierarchy in `src/exceptions.py`
    - Add ChunkViewerError, TraceError, LineageError, ClassificationError, ProcessingError subclasses
    - Add SelectionError, BatchError, TemplateError, WebhookError subclasses
    - Follow existing RAGSystemError pattern
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 1.2 Create core data models in `src/models/query_pipeline.py`
    - Implement QueryType enum, QueryClassification, FileCandidate, SheetCandidate dataclasses
    - Implement Citation, ConfidenceBreakdown, QueryResponse Pydantic models
    - Implement ClarificationRequest model
    - _Requirements: 6.1, 11.1, 11.2, 11.4, 11.8_

  - [x] 1.3 Create chunk visibility models in `src/models/chunk_visibility.py`
    - Implement ChunkDetails, ExtractionMetadata, ChunkVersion dataclasses
    - Implement ChunkFilters, PaginatedChunkResponse, ChunkFeedback models
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 1.7, 3.1, 3.5_

  - [x] 1.4 Create traceability models in `src/models/traceability.py`
    - Implement QueryTrace, DataLineage, FileSelectionDecision, SheetSelectionDecision dataclasses
    - _Requirements: 16.2, 17.1_

  - [x] 1.5 Create Excel-specific models in `src/models/excel_features.py`
    - Implement FormulaCell, MergedCellInfo, NamedRange, ExcelTable dataclasses
    - Implement ConditionalFormat, DataValidation, ExtractionWarning dataclasses
    - Implement EnhancedExtractionResult dataclass
    - _Requirements: 18.1, 19.2, 20.1, 30.1, 32.1, 35.1_

  - [x] 1.6 Create batch, template, webhook, and access control models in `src/models/enterprise.py`
    - Implement BatchQueryRequest, BatchQueryStatus, QueryTemplate models
    - Implement WebhookRegistration, WebhookDelivery models
    - Implement UserRole enum, AccessControlEntry, AccessAuditLog dataclasses
    - _Requirements: 24.1, 25.1, 28.1, 29.1_

- [x] 2. Database Schema Extensions
  - [x] 2.1 Create database migration for new tables in `src/database/migrations/`
    - Add chunk_versions table with version tracking
    - Add query_traces table for audit
    - Add data_lineage table for traceability
    - Add extraction_metadata table
    - Add chunk_feedback table
    - _Requirements: 16.2, 16.5, 17.1, 21.1, 27.1_

  - [x] 2.2 Add enterprise tables to migration
    - Add query_templates table
    - Add webhooks and webhook_deliveries tables
    - Add file_access_control and access_audit_log tables
    - Add named_ranges and excel_tables tables
    - Add query_cache table
    - _Requirements: 25.1, 28.1, 29.1, 32.1, 43.1_

  - [x] 2.3 Create database indexes for performance
    - Add indexes on chunk_versions(file_id, chunk_id)
    - Add indexes on query_traces(user_id, session_id, created_at)
    - Add indexes on data_lineage(trace_id, file_id)
    - Add indexes on access_audit_log(user_id, created_at)
    - _Requirements: 15.1, 15.5_

- [x] 3. Checkpoint - Foundation Complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Enhanced Extraction Layer
  - [x] 4.1 Create EnhancedExtractionStrategy abstract base class in `src/extraction/enhanced_strategy.py`
    - Define abstract methods: extract, detect_formulas, detect_merged_cells, detect_named_ranges
    - Define abstract methods: detect_pivot_tables, detect_charts, detect_hidden_content
    - Follow DIP - all dependencies injected
    - _Requirements: 18.1, 19.1, 20.1, 30.1, 31.1_

  - [x] 4.2 Implement EnhancedOpenpyxlExtractor in `src/extraction/enhanced_openpyxl.py`
    - Implement formula cell extraction with formula_text and computed_value
    - Implement merged cell detection and expansion
    - Implement named range and Excel table detection
    - Implement pivot table and chart detection
    - Implement hidden row/column/sheet detection
    - _Requirements: 18.1, 18.2, 19.1, 19.2, 20.1, 30.1, 31.1, 32.1_

  - [ ]* 4.3 Write property test for formula cell extraction
    - **Property 19: Formula Cell Extraction**
    - **Validates: Requirements 18.1, 18.2**

  - [ ]* 4.4 Write property test for merged cell expansion
    - **Property 20: Merged Cell Expansion**
    - **Validates: Requirements 30.1, 30.2, 30.3**

  - [x] 4.5 Implement ExtractionQualityScorer in `src/extraction/quality_scorer.py`
    - Compute quality_score from data_completeness, structure_clarity, has_headers, has_data, error_count
    - Score must be in range [0.0, 1.0]
    - Flag files with quality < 0.5 as problematic
    - _Requirements: 22.1, 22.2, 22.3, 22.4_

  - [ ]* 4.6 Write property test for quality score computation
    - **Property 22: Quality Score Computation**
    - **Validates: Requirements 22.1, 22.2, 22.3**

  - [x] 4.7 Implement language detection in extraction
    - Detect primary language of Excel content
    - Store detected language in chunk metadata
    - _Requirements: 23.1, 23.3_

- [ ] 5. Chunk Viewer Core
  - [x] 5.1 Create ChunkMetadataStore in `src/chunk_viewer/metadata_store.py`
    - Implement CRUD operations for chunk metadata
    - Support filtering by file_id, sheet_name, extraction_strategy, content_type
    - Use connection pooling for database access
    - _Requirements: 1.1, 1.3, 2.2_

  - [x] 5.2 Create ChunkVersionStore in `src/chunk_viewer/version_store.py`
    - Implement version creation on re-indexing
    - Implement version history retrieval
    - Implement diff comparison between versions
    - Support rollback to previous version
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5_

  - [ ]* 5.3 Write property test for chunk version preservation
    - **Property 21: Chunk Version Preservation**
    - **Validates: Requirements 21.1, 21.2, 21.3, 21.4**

  - [x] 5.4 Create ChunkViewer service in `src/chunk_viewer/viewer.py`
    - Implement get_chunks_for_file with pagination
    - Implement get_chunks_for_sheet with filtering
    - Implement search_chunks with semantic similarity
    - Implement get_extraction_metadata
    - Implement compare_extraction_strategies
    - All dependencies injected via constructor
    - _Requirements: 1.1, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 3.1, 3.6_

  - [ ]* 5.5 Write property test for chunk data completeness
    - **Property 1: Chunk Data Completeness**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.6, 1.7, 1.8**

  - [ ]* 5.6 Write property test for chunk sheet filtering
    - **Property 2: Chunk Sheet Filtering**
    - **Validates: Requirements 1.4, 2.2, 2.3**

  - [ ]* 5.7 Write property test for pagination bounds
    - **Property 3: Pagination Bounds**
    - **Validates: Requirements 1.5**

  - [ ]* 5.8 Write property test for semantic search ordering
    - **Property 4: Semantic Search Ordering**
    - **Validates: Requirements 2.1, 2.4**

  - [x] 5.9 Create FeedbackCollector in `src/chunk_viewer/feedback.py`
    - Implement feedback submission with types: incorrect_data, missing_data, wrong_boundaries, extraction_error, other
    - Implement feedback aggregation and summary
    - Flag chunks with multiple negative reports
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5_

- [ ]* 6. Checkpoint - Chunk Viewer Complete
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. File and Sheet Selection
  - [x] 7.1 Create FileSelector in `src/query_pipeline/file_selector.py`
    - Implement rank_files with weighted scoring: semantic (50%), metadata (30%), preference (20%)
    - Implement threshold behavior: auto-select >0.9, clarify 0.5-0.9, low-confidence <0.5
    - Implement temporal reference boosting for date patterns
    - Record user selections for preference learning
    - Provide explainability for ranking decisions
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ]* 7.2 Write property test for file selection scoring formula
    - **Property 5: File Selection Scoring Formula**
    - **Validates: Requirements 4.1**

  - [ ]* 7.3 Write property test for file selection threshold behavior
    - **Property 6: File Selection Threshold Behavior**
    - **Validates: Requirements 4.2, 4.3, 4.4**

  - [x] 7.4 Create SheetSelector in `src/query_pipeline/sheet_selector.py`
    - Implement rank_sheets with weighted scoring: name (30%), header (40%), data_type (20%), content (10%)
    - Implement threshold behavior: auto-select >0.7, multi-sheet combination, clarify <0.5
    - Determine combination strategy (union, join, separate) for multi-sheet queries
    - Provide explainability for ranking decisions
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ]* 7.5 Write property test for sheet selection scoring formula
    - **Property 7: Sheet Selection Scoring Formula**
    - **Validates: Requirements 5.1**

  - [ ]* 7.6 Write property test for sheet selection threshold behavior
    - **Property 8: Sheet Selection Threshold Behavior**
    - **Validates: Requirements 5.2, 5.3, 5.4**

- [x] 8. Query Classification
  - [x] 8.1 Create QueryClassifier in `src/query_pipeline/classifier.py`
    - Implement keyword-based classification for aggregation, lookup, summarization, comparison
    - Use LLM for ambiguous cases
    - Return confidence score and alternative types when confidence < 0.6
    - Extract detected aggregations, filters, and columns
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 8.2 Write property test for query classification validity
    - **Property 9: Query Classification Validity**
    - **Validates: Requirements 6.1, 6.6**

  - [ ]* 8.3 Write property test for query classification keyword detection
    - **Property 10: Query Classification Keyword Detection**
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5**

  - [ ]* 8.4 Write property test for low confidence classification alternatives
    - **Property 11: Low Confidence Classification Alternatives**
    - **Validates: Requirements 6.7**

- [ ]* 9. Checkpoint - Selection and Classification Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Query Processors
  - [x] 10.1 Create QueryProcessorRegistry in `src/query_pipeline/processor_registry.py`
    - Implement registry pattern with @register decorator
    - Support get_processor by QueryType
    - Follow OCP - new processors added without modifying registry
    - _Requirements: 7.1, 8.1, 9.1, 10.1_

  - [x] 10.2 Create BaseQueryProcessor abstract class in `src/query_pipeline/processors/base.py`
    - Define abstract process method
    - Define can_process method
    - _Requirements: 7.1, 8.1, 9.1, 10.1_

  - [x] 10.3 Implement AggregationProcessor in `src/query_pipeline/processors/aggregation.py`
    - Support SUM, AVERAGE, COUNT, MIN, MAX, MEDIAN functions
    - Implement filter condition parsing and application
    - Validate numeric data types, skip non-numeric with warning
    - Return computed value, rows processed, rows skipped
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 10.4 Write property test for aggregation computation correctness
    - **Property 12: Aggregation Computation Correctness**
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.6**

  - [x] 10.5 Implement LookupProcessor in `src/query_pipeline/processors/lookup.py`
    - Support lookups by row criteria, column name, cell reference
    - Return all matching rows up to configurable limit (default 10)
    - Preserve original data formatting (dates, currency, percentages)
    - Suggest similar values when no matches found
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 10.6 Write property test for lookup result matching
    - **Property 13: Lookup Result Matching**
    - **Validates: Requirements 8.1, 8.2, 8.3**

  - [x] 10.7 Implement SummarizationProcessor in `src/query_pipeline/processors/summarization.py`
    - Generate natural language summaries using LLM
    - Include key statistics: row count, column count, date range, numeric ranges
    - Identify patterns, outliers, trends
    - Use sampling for large datasets (>1000 rows)
    - Limit summary to 500 words unless requested otherwise
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 10.8 Implement ComparisonProcessor in `src/query_pipeline/processors/comparison.py`
    - Identify entities being compared (files, sheets, time periods, categories)
    - Align data structures using common columns
    - Calculate absolute and percentage differences
    - Identify trends and growth rates for temporal comparisons
    - Return error for incompatible structures
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ]* 10.9 Write property test for comparison difference correctness
    - **Property 14: Comparison Difference Correctness**
    - **Validates: Requirements 10.3, 10.4**

- [x] 11. Answer Generator
  - [x] 11.1 Create AnswerGenerator in `src/query_pipeline/answer_generator.py`
    - Include source citations for every factual claim
    - Format citations as [File: filename, Sheet: sheetname, Range: cellrange]
    - Include confidence score and breakdown (file, sheet, data)
    - Add disclaimer when confidence < 0.7
    - Preserve numeric precision from source data
    - Provide navigable citations with lineage_id
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [ ]* 11.2 Write property test for citation format validity
    - **Property 15: Citation Format Validity**
    - **Validates: Requirements 11.2**

  - [ ]* 11.3 Write property test for confidence disclaimer presence
    - **Property 16: Confidence Disclaimer Presence**
    - **Validates: Requirements 11.5**

- [ ]* 12. Checkpoint - Query Processors Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Traceability Layer
  - [x] 13.1 Create TraceStorage in `src/traceability/trace_storage.py`
    - Implement CRUD for QueryTrace records
    - Support configurable retention period (default 90 days)
    - Implement trace expiration cleanup
    - _Requirements: 16.2, 16.5_

  - [x] 13.2 Create TraceRecorder in `src/traceability/trace_recorder.py`
    - Implement start_trace, record_file_selection, record_sheet_selection
    - Implement record_classification, record_retrieval, complete_trace
    - Generate unique trace_id for every query
    - Include reasoning explanations for each decision
    - Support export in JSON and CSV formats
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_

  - [ ]* 13.3 Write property test for trace completeness
    - **Property 17: Trace Completeness**
    - **Validates: Requirements 16.1, 16.2, 16.4**

  - [x] 13.4 Create LineageStorage in `src/traceability/lineage_storage.py`
    - Implement CRUD for DataLineage records
    - Link answer components to source cells
    - _Requirements: 17.1, 17.3_

  - [x] 13.5 Create DataLineageTracker in `src/traceability/lineage_tracker.py`
    - Create lineage records linking answers to sources
    - Include file_id, sheet_name, cell_range, chunk_id, embedding_id
    - Track indexed_at and last_verified_at timestamps
    - Implement staleness detection when source data changes
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [ ]* 13.6 Write property test for data lineage chain
    - **Property 18: Data Lineage Chain**
    - **Validates: Requirements 17.1, 17.2, 17.3**

- [x] 14. Query Pipeline Orchestrator
  - [x] 14.1 Create QueryPipelineOrchestrator in `src/query_pipeline/orchestrator.py`
    - Coordinate file selection, sheet selection, classification, processing, answer generation
    - Implement process_query with full pipeline execution
    - Implement handle_clarification for user responses
    - Support session-based context for multi-turn conversations
    - Implement timeout handling (default 30 seconds)
    - All dependencies injected via constructor
    - _Requirements: 4.1, 5.1, 6.1, 7.1, 11.1, 12.6, 14.6_

  - [x] 14.2 Implement error handling in orchestrator
    - Return appropriate errors for no indexed files, ambiguous data, data type issues
    - Return suggestions for similar names when file/sheet not found
    - Log full error details with correlation ID
    - Return user-friendly messages
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ]* 15. Checkpoint - Core Pipeline Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Access Control
  - [x] 16.1 Create AccessController in `src/access_control/controller.py`
    - Implement role-based access control: admin, developer, analyst, viewer
    - Support file-level access restrictions
    - Return 403 Forbidden for unauthorized access
    - Log all access attempts for audit
    - Support data masking for sensitive columns
    - _Requirements: 29.1, 29.2, 29.3, 29.4, 29.5_

  - [ ]* 16.2 Write property test for access control enforcement
    - **Property 23: Access Control Enforcement**
    - **Validates: Requirements 29.1, 29.2, 29.3**

- [x] 17. Caching Layer
  - [x] 17.1 Create QueryCache in `src/cache/query_cache.py`
    - Cache query results with configurable TTL (default 1 hour)
    - Implement intelligent cache key generation for semantically equivalent queries
    - Track file_ids for cache invalidation
    - Support cache bypass option
    - Indicate cache hit in responses
    - _Requirements: 43.1, 43.3, 43.4, 43.5_

  - [x] 17.2 Implement cache invalidation on re-indexing
    - Invalidate all cache entries containing re-indexed file_id
    - _Requirements: 43.2_

  - [ ]* 17.3 Write property test for cache hit consistency
    - **Property 26: Cache Hit Consistency**
    - **Validates: Requirements 43.1, 43.3**

  - [ ]* 17.4 Write property test for cache invalidation on re-index
    - **Property 27: Cache Invalidation on Re-index**
    - **Validates: Requirements 43.2**

- [x] 18. Date and Intelligence Features
  - [x] 18.1 Create DateParser in `src/intelligence/date_parser.py`
    - Parse natural language date references: "last quarter", "YTD", "January 2024", "past 6 months"
    - Support fiscal year configurations
    - Handle multiple date formats: MM/DD/YYYY, DD/MM/YYYY, YYYY-MM-DD
    - _Requirements: 33.1, 33.4, 33.6_

  - [ ]* 18.2 Write property test for date reference parsing
    - **Property 28: Date Reference Parsing**
    - **Validates: Requirements 33.1, 33.4**

  - [x] 18.3 Create UnitAwarenessService in `src/intelligence/unit_awareness.py`
    - Detect and preserve unit information ($, €, %, kg, miles)
    - Perform unit-aware aggregations
    - Warn on unit mismatch in comparisons
    - Include units in numeric answers
    - _Requirements: 34.1, 34.2, 34.3, 34.4_

  - [x] 18.4 Create AnomalyDetector in `src/intelligence/anomaly_detector.py`
    - Detect numeric outliers using IQR and Z-score
    - Detect missing values, duplicates, inconsistent formatting
    - _Requirements: 38.1, 38.2, 38.3, 38.4_

  - [x] 18.5 Create RelationshipDetector in `src/intelligence/relationship_detector.py`
    - Detect relationships between files based on common columns
    - Support implicit joins across files
    - Suggest related files during selection
    - _Requirements: 36.1, 36.2, 36.3, 36.4_

- [ ]* 19. Checkpoint - Intelligence Features Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Batch and Template Features
  - [x] 20.1 Create BatchQueryProcessor in `src/batch/processor.py`
    - Accept array of queries (max 100)
    - Process queries in parallel where possible
    - Return results in order with individual status
    - Continue processing on partial failures
    - Support progress tracking via batch_id
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 24.5_

  - [ ]* 20.2 Write property test for batch query result ordering
    - **Property 25: Batch Query Result Ordering**
    - **Validates: Requirements 24.2, 24.3, 24.4**

  - [x] 20.3 Create TemplateManager in `src/templates/manager.py`
    - Support parameterized templates with {{parameter_name}} syntax
    - Extract parameters from template text
    - Execute templates with parameter substitution
    - Support template sharing within organization
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_

  - [ ]* 20.4 Write property test for template parameter substitution
    - **Property 24: Template Parameter Substitution**
    - **Validates: Requirements 25.2, 25.3**

- [x] 21. Webhook System
  - [x] 21.1 Create WebhookManager in `src/webhooks/manager.py`
    - Support registration for events: indexing_complete, query_failed, low_confidence_answer, batch_complete
    - Implement delivery with retry (3 attempts, exponential backoff)
    - Track delivery history and status
    - _Requirements: 28.1, 28.2, 28.3, 28.4, 28.5_

- [x] 22. Export Capabilities
  - [x] 22.1 Create ExportService in `src/export/service.py`
    - Support export to CSV, Excel (.xlsx), JSON formats
    - Preserve data types and formatting for Excel export
    - Support scheduled exports for recurring reports
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5_

- [x] 23. Chunk Visibility API Endpoints
  - [x] 23.1 Create chunk visibility routes in `src/api/routes/chunks.py`
    - GET /api/v1/chunks/{file_id} - all chunks for file with pagination
    - GET /api/v1/chunks/{file_id}/sheets/{sheet_name} - chunks for sheet
    - POST /api/v1/chunks/search - semantic search with filters
    - GET /api/v1/files/{file_id}/extraction-metadata - extraction details
    - GET /api/v1/chunks/{file_id}/versions - version history
    - POST /api/v1/chunks/{chunk_id}/feedback - submit feedback
    - GET /api/v1/chunks/feedback-summary - aggregated feedback
    - GET /api/v1/files/quality-report - quality scores for all files
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 21.2, 22.5, 27.1, 27.4_

  - [ ]* 23.2 Write property test for API response schema compliance
    - **Property 29: API Response Schema Compliance**
    - **Validates: Requirements 13.5, 14.5**

  - [ ]* 23.3 Write property test for extraction metadata completeness
    - **Property 30: Extraction Metadata Completeness**
    - **Validates: Requirements 3.1, 3.5**

- [x] 24. Query Pipeline API Endpoints
  - [x] 24.1 Create query pipeline routes in `src/api/routes/query.py`
    - POST /api/v1/query/smart - process natural language query
    - POST /api/v1/query/clarify - respond to clarification
    - GET /api/v1/query/classify - get query classification
    - GET /api/v1/query/trace/{trace_id} - get query trace
    - GET /api/v1/lineage/{lineage_id} - get data lineage
    - Support streaming via Server-Sent Events for long queries
    - Include processing_time_ms, query_type, confidence in responses
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 16.3, 17.3_

  - [x] 24.2 Create batch and template routes in `src/api/routes/batch.py`
    - POST /api/v1/query/batch - submit batch queries
    - GET /api/v1/query/batch/{batch_id}/status - batch status
    - POST /api/v1/query/templates - create template
    - POST /api/v1/query/templates/{template_id}/execute - execute template
    - GET /api/v1/query/templates - list templates
    - _Requirements: 24.1, 24.5, 25.1, 25.3, 25.4_

  - [x] 24.3 Create export and webhook routes in `src/api/routes/export.py`
    - POST /api/v1/export - export results
    - POST /api/v1/webhooks - register webhook
    - GET /api/v1/webhooks/{webhook_id}/deliveries - delivery history
    - _Requirements: 26.3, 28.2, 28.5_

  - [x] 24.4 Create intelligence routes in `src/api/routes/intelligence.py`
    - GET /api/v1/query/suggestions - query suggestions
    - GET /api/v1/files/{file_id}/anomalies - detected anomalies
    - GET /api/v1/usage/summary - query cost statistics
    - _Requirements: 37.1, 38.5, 42.4_

- [ ]* 25. Checkpoint - API Layer Complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 26. Performance and Scale Features
  - [x] 26.1 Implement streaming extraction for large files in `src/extraction/streaming.py`
    - Support files larger than 100MB
    - Implement chunked processing for sheets >1M rows
    - Configure memory limits with graceful degradation
    - _Requirements: 40.1, 40.2, 40.5_

  - [x] 26.2 Implement incremental indexing in `src/extraction/incremental.py`
    - Detect file modifications using checksums
    - Identify which chunks need updating
    - Support forced full re-indexing option
    - _Requirements: 39.1, 39.2, 39.3, 39.4, 39.5_

  - [x] 26.3 Implement query cost estimation in `src/query_pipeline/cost_estimator.py`
    - Estimate cost based on files to scan, rows to process, complexity
    - Support cost limits that reject expensive queries
    - Suggest ways to reduce query scope when rejected
    - _Requirements: 42.1, 42.2, 42.3, 42.5_

  - [x] 26.4 Add performance logging and monitoring
    - Log warnings when performance thresholds exceeded
    - Track timing for file selection (<500ms), sheet selection (<200ms)
    - Track timing for aggregation (<2s), lookup (<1s), chunk listing (<500ms)
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_

- [x] 27. Integration and Wiring
  - [x] 27.1 Create dependency injection container in `src/container.py`
    - Wire all components with proper dependency injection
    - Follow DIP - depend on abstractions
    - No module-level state
    - _Requirements: All (SOLID compliance)_

  - [x] 27.2 Register all API routes in `src/api/main.py`
    - Mount chunk visibility routes
    - Mount query pipeline routes
    - Mount batch, export, webhook routes
    - Mount intelligence routes
    - _Requirements: 13.1-13.6, 14.1-14.6_

  - [x] 27.3 Create configuration module in `src/config/query_pipeline.py`
    - Define all configurable parameters with defaults
    - Support environment variable overrides
    - Document all configuration options
    - _Requirements: All (configuration requirements)_

- [ ] 28. Final Checkpoint - All Tests Pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests that can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical boundaries
- Property tests validate the 30 correctness properties defined in the design document
- All components follow SOLID principles with dependency injection
- No module-level state - use injected services for state management
- Type hints required on all functions per coding standards
- Use registry patterns for extensibility (query processors, extraction strategies)

## Property Test Summary

| Property | Description | Requirements |
|----------|-------------|--------------|
| 1 | Chunk Data Completeness | 1.1, 1.2, 1.3, 1.6, 1.7, 1.8 |
| 2 | Chunk Sheet Filtering | 1.4, 2.2, 2.3 |
| 3 | Pagination Bounds | 1.5 |
| 4 | Semantic Search Ordering | 2.1, 2.4 |
| 5 | File Selection Scoring Formula | 4.1 |
| 6 | File Selection Threshold Behavior | 4.2, 4.3, 4.4 |
| 7 | Sheet Selection Scoring Formula | 5.1 |
| 8 | Sheet Selection Threshold Behavior | 5.2, 5.3, 5.4 |
| 9 | Query Classification Validity | 6.1, 6.6 |
| 10 | Query Classification Keyword Detection | 6.2, 6.3, 6.4, 6.5 |
| 11 | Low Confidence Classification Alternatives | 6.7 |
| 12 | Aggregation Computation Correctness | 7.1, 7.2, 7.3, 7.4, 7.6 |
| 13 | Lookup Result Matching | 8.1, 8.2, 8.3 |
| 14 | Comparison Difference Correctness | 10.3, 10.4 |
| 15 | Citation Format Validity | 11.2 |
| 16 | Confidence Disclaimer Presence | 11.5 |
| 17 | Trace Completeness | 16.1, 16.2, 16.4 |
| 18 | Data Lineage Chain | 17.1, 17.2, 17.3 |
| 19 | Formula Cell Extraction | 18.1, 18.2 |
| 20 | Merged Cell Expansion | 30.1, 30.2, 30.3 |
| 21 | Chunk Version Preservation | 21.1, 21.2, 21.3, 21.4 |
| 22 | Quality Score Computation | 22.1, 22.2, 22.3 |
| 23 | Access Control Enforcement | 29.1, 29.2, 29.3 |
| 24 | Template Parameter Substitution | 25.2, 25.3 |
| 25 | Batch Query Result Ordering | 24.2, 24.3, 24.4 |
| 26 | Cache Hit Consistency | 43.1, 43.3 |
| 27 | Cache Invalidation on Re-index | 43.2 |
| 28 | Date Reference Parsing | 33.1, 33.4 |
| 29 | API Response Schema Compliance | 13.5, 14.5 |
| 30 | Extraction Metadata Completeness | 3.1, 3.5 |
