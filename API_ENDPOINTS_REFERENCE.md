# API Endpoints Reference

## Base URL

- Development: `http://localhost:8000`
- Production: Configure as needed

## Authentication

All endpoints except `/api/auth/login` require authentication via JWT token:

```
Authorization: Bearer <token>
```

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [File Management](#2-file-management)
3. [Google Drive Configuration](#3-google-drive-configuration)
4. [Chat Sessions](#4-chat-sessions)
5. [Chunk Visibility (NEW)](#5-chunk-visibility-new)
6. [Smart Query Pipeline (NEW)](#6-smart-query-pipeline-new)
7. [Batch Processing (NEW)](#7-batch-processing-new)
8. [Query Templates (NEW)](#8-query-templates-new)
9. [Export (NEW)](#9-export-new)
10. [Webhooks (NEW)](#10-webhooks-new)
11. [Intelligence (NEW)](#11-intelligence-new)
12. [Traceability (NEW)](#12-traceability-new)

---

## 1. Authentication

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "girish",
  "password": "Girish@123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 86400,
  "username": "girish"
}
```

### Logout
```http
POST /api/auth/logout
Authorization: Bearer <token>
```

### Check Status
```http
GET /api/auth/status
Authorization: Bearer <token>
```

---

## 2. File Management

### Upload File
```http
POST /api/files/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <Excel file>
```

### List Files
```http
GET /api/files/list?page=1&page_size=20
Authorization: Bearer <token>
```

### Delete File
```http
DELETE /api/files/{file_id}
Authorization: Bearer <token>
```

### Reindex File
```http
POST /api/files/{file_id}/reindex
Authorization: Bearer <token>
```

---

## 3. Google Drive Configuration

### Connect to Google Drive
```http
POST /api/config/gdrive/connect
Authorization: Bearer <token>
```

### OAuth Callback
```http
GET /api/config/gdrive/callback?code=<auth_code>&state=<state>
```

### Disconnect
```http
DELETE /api/config/gdrive/disconnect
Authorization: Bearer <token>
```

### Check Status
```http
GET /api/config/gdrive/status
Authorization: Bearer <token>
```

---

## 4. Chat Sessions

### Submit Query
```http
POST /api/chat/query
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "What is the total expense in January?",
  "session_id": "session_123"
}
```

**Response (200 OK):**
```json
{
  "answer": "The total expense in January is $15,234.50",
  "sources": [
    {
      "file_name": "expenses_jan2024.xlsx",
      "sheet_name": "Summary",
      "cell_range": "B10",
      "citation_text": "Source: expenses_jan2024.xlsx, Sheet: Summary, Cell: B10"
    }
  ],
  "confidence": 95.5,
  "session_id": "session_123",
  "requires_clarification": false,
  "processing_time_ms": 1234.56
}
```

### List Sessions
```http
GET /api/chat/sessions
Authorization: Bearer <token>
```

### Get Session History
```http
GET /api/chat/sessions/{session_id}/history
Authorization: Bearer <token>
```

### Delete Session
```http
DELETE /api/chat/sessions/{session_id}
Authorization: Bearer <token>
```

---

## 5. Chunk Visibility (NEW)

### Get Chunks for File
```http
GET /api/v1/chunks/{file_id}?page=1&page_size=20
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "chunks": [
    {
      "chunk_id": "chunk_001",
      "file_id": "file_123",
      "file_name": "sales_2024.xlsx",
      "sheet_name": "Q1",
      "chunk_index": 0,
      "chunk_text": "Product, Revenue, Units...",
      "raw_source_data": "A1:D50",
      "start_row": 1,
      "end_row": 50,
      "overlap_rows": 5,
      "extraction_strategy": "openpyxl",
      "content_type": "data",
      "row_count": 50,
      "column_count": 4,
      "embedding_dimensions": 1024,
      "token_count": 256,
      "embedding_model": "bge-m3"
    }
  ],
  "total_count": 150,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

### Get Chunks for Sheet
```http
GET /api/v1/chunks/{file_id}/sheets/{sheet_name}?page=1&page_size=20
Authorization: Bearer <token>
```

### Search Chunks
```http
POST /api/v1/chunks/search
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "revenue data",
  "filters": {
    "extraction_strategy": "openpyxl",
    "file_id": "file_123",
    "sheet_name": "Q1",
    "content_type": "data",
    "min_quality_score": 0.7
  },
  "page": 1,
  "page_size": 20
}
```

**Response (200 OK):**
```json
{
  "chunks": [
    {
      "chunk_id": "chunk_001",
      "similarity_score": 0.92,
      ...
    }
  ],
  "total_count": 25,
  "page": 1,
  "page_size": 20,
  "has_more": true
}
```

### Get Extraction Metadata
```http
GET /api/v1/files/{file_id}/extraction-metadata
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "file_id": "file_123",
  "strategy_used": "openpyxl",
  "strategy_selected_reason": "File contains pivot tables",
  "complexity_score": 0.75,
  "quality_score": 0.92,
  "has_headers": true,
  "has_data": true,
  "data_completeness": 0.95,
  "structure_clarity": 0.88,
  "extraction_errors": [],
  "extraction_warnings": ["Hidden sheet detected: Archive"],
  "fallback_used": false,
  "extraction_duration_ms": 1250,
  "extracted_at": "2024-01-15T10:00:00Z"
}
```

### Get Chunk Versions
```http
GET /api/v1/chunks/{file_id}/versions
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "file_id": "file_123",
  "versions": [
    {
      "version_id": "v_002",
      "version_number": 2,
      "indexed_at": "2024-01-15T10:00:00Z",
      "extraction_strategy": "openpyxl",
      "change_summary": "5 chunks added, 2 modified"
    },
    {
      "version_id": "v_001",
      "version_number": 1,
      "indexed_at": "2024-01-10T10:00:00Z",
      "extraction_strategy": "openpyxl",
      "change_summary": "Initial indexing"
    }
  ]
}
```

### Submit Chunk Feedback
```http
POST /api/v1/chunks/{chunk_id}/feedback
Authorization: Bearer <token>
Content-Type: application/json

{
  "feedback_type": "incorrect_data",
  "rating": 2,
  "comment": "Missing some rows from the original data"
}
```

**Feedback Types:** `incorrect_data`, `missing_data`, `wrong_boundaries`, `extraction_error`, `other`

### Get Feedback Summary
```http
GET /api/v1/chunks/feedback-summary
Authorization: Bearer <token>
```

### Get Quality Report
```http
GET /api/v1/files/quality-report
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "files": [
    {
      "file_id": "file_123",
      "file_name": "sales_2024.xlsx",
      "quality_score": 0.92,
      "is_problematic": false,
      "issues": []
    },
    {
      "file_id": "file_456",
      "file_name": "legacy_data.xls",
      "quality_score": 0.45,
      "is_problematic": true,
      "issues": ["Low structure clarity", "Missing headers"]
    }
  ],
  "total_files": 50,
  "problematic_count": 3
}
```

---

## 6. Smart Query Pipeline (NEW)

### Process Smart Query
```http
POST /api/v1/query/smart
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "What was the total revenue in Q1 2024?",
  "session_id": "session_123",
  "file_hints": ["sales_2024.xlsx"],
  "sheet_hints": ["Q1"]
}
```

**Response (200 OK):**
```json
{
  "answer": "The total revenue in Q1 2024 was $1,234,567",
  "citations": [
    {
      "file_name": "sales_2024.xlsx",
      "sheet_name": "Q1",
      "cell_range": "B2:B100",
      "lineage_id": "lin_abc123"
    }
  ],
  "confidence": 0.95,
  "confidence_breakdown": {
    "file_confidence": 0.96,
    "sheet_confidence": 0.94,
    "data_confidence": 0.95,
    "overall_confidence": 0.95
  },
  "query_type": "aggregation",
  "trace_id": "tr_abc123",
  "processing_time_ms": 1250,
  "from_cache": false
}
```

**Response with Clarification:**
```json
{
  "answer": null,
  "requires_clarification": true,
  "clarification_type": "file",
  "clarification_message": "Multiple files match your query. Which file did you mean?",
  "clarification_options": [
    {
      "option_id": "opt_1",
      "description": "sales_2024.xlsx",
      "confidence": 0.75
    },
    {
      "option_id": "opt_2",
      "description": "sales_2023.xlsx",
      "confidence": 0.65
    }
  ],
  "session_id": "session_123",
  "pending_query": "What was the total revenue in Q1?"
}
```

### Respond to Clarification
```http
POST /api/v1/query/clarify
Authorization: Bearer <token>
Content-Type: application/json

{
  "session_id": "session_123",
  "clarification_type": "file",
  "selected_value": "opt_1"
}
```

### Classify Query
```http
GET /api/v1/query/classify?query=What%20is%20the%20total%20revenue
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "query_type": "aggregation",
  "confidence": 0.95,
  "alternative_types": [
    {"type": "lookup", "confidence": 0.15}
  ],
  "detected_aggregations": ["SUM"],
  "detected_filters": [],
  "detected_columns": ["revenue"]
}
```

---

## 7. Batch Processing (NEW)

### Submit Batch Queries
```http
POST /api/v1/query/batch
Authorization: Bearer <token>
Content-Type: application/json

{
  "queries": [
    "What was the total revenue in Q1?",
    "What was the total revenue in Q2?",
    "Compare Q1 and Q2 expenses"
  ],
  "file_hints": ["financial_2024.xlsx"]
}
```

**Response (200 OK):**
```json
{
  "batch_id": "batch_abc123",
  "total_queries": 3,
  "status": "processing",
  "message": "Batch submitted successfully"
}
```

### Get Batch Status
```http
GET /api/v1/query/batch/{batch_id}/status
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "batch_id": "batch_abc123",
  "total_queries": 3,
  "completed": 2,
  "failed": 0,
  "status": "processing",
  "results": [
    {
      "query_index": 0,
      "status": "completed",
      "answer": "The total revenue in Q1 was $1,234,567",
      "processing_time_ms": 1100
    },
    {
      "query_index": 1,
      "status": "completed",
      "answer": "The total revenue in Q2 was $1,456,789",
      "processing_time_ms": 980
    },
    {
      "query_index": 2,
      "status": "pending"
    }
  ]
}
```

---

## 8. Query Templates (NEW)

### Create Template
```http
POST /api/v1/query/templates
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Quarterly Revenue",
  "template_text": "What was the total {{metric}} in {{quarter}} {{year}}?",
  "is_shared": true
}
```

**Response (200 OK):**
```json
{
  "template_id": "tmpl_abc123",
  "name": "Quarterly Revenue",
  "template_text": "What was the total {{metric}} in {{quarter}} {{year}}?",
  "parameters": ["metric", "quarter", "year"],
  "created_by": "girish",
  "is_shared": true,
  "created_at": "2024-01-15T10:00:00Z"
}
```

### List Templates
```http
GET /api/v1/query/templates
Authorization: Bearer <token>
```

### Execute Template
```http
POST /api/v1/query/templates/{template_id}/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "parameters": {
    "metric": "revenue",
    "quarter": "Q1",
    "year": "2024"
  }
}
```

**Response:** Same as Smart Query response

---

## 9. Export (NEW)

### Export Results
```http
POST /api/v1/export
Authorization: Bearer <token>
Content-Type: application/json

{
  "result_id": "tr_abc123",
  "format": "xlsx",
  "include_metadata": true
}
```

**Formats:** `csv`, `xlsx`, `json`

**Response (200 OK):**
```json
{
  "export_id": "exp_abc123",
  "status": "completed",
  "download_url": "/api/v1/export/exp_abc123/download",
  "expires_at": "2024-01-15T11:00:00Z"
}
```

---

## 10. Webhooks (NEW)

### Register Webhook
```http
POST /api/v1/webhooks
Authorization: Bearer <token>
Content-Type: application/json

{
  "url": "https://example.com/webhook",
  "events": ["indexing_complete", "query_failed", "low_confidence_answer"],
  "secret": "optional_secret_for_signature"
}
```

**Events:** `indexing_complete`, `query_failed`, `low_confidence_answer`, `batch_complete`

**Response (200 OK):**
```json
{
  "webhook_id": "wh_abc123",
  "url": "https://example.com/webhook",
  "events": ["indexing_complete", "query_failed", "low_confidence_answer"],
  "is_active": true,
  "created_at": "2024-01-15T10:00:00Z"
}
```

### Get Delivery History
```http
GET /api/v1/webhooks/{webhook_id}/deliveries
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "webhook_id": "wh_abc123",
  "deliveries": [
    {
      "delivery_id": "del_001",
      "event_type": "indexing_complete",
      "status": "delivered",
      "attempts": 1,
      "last_attempt_at": "2024-01-15T10:05:00Z",
      "response_code": 200
    },
    {
      "delivery_id": "del_002",
      "event_type": "query_failed",
      "status": "failed",
      "attempts": 3,
      "last_attempt_at": "2024-01-15T10:10:00Z",
      "response_code": 500
    }
  ]
}
```

---

## 11. Intelligence (NEW)

### Get Query Suggestions
```http
GET /api/v1/query/suggestions?context=sales
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "suggestions": [
    "What was the total sales revenue?",
    "Compare sales by quarter",
    "Show top 10 products by sales"
  ]
}
```

### Get File Anomalies
```http
GET /api/v1/files/{file_id}/anomalies
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "file_id": "file_123",
  "anomalies": [
    {
      "type": "outlier",
      "sheet_name": "Q1",
      "column": "Revenue",
      "row": 45,
      "value": 999999999,
      "message": "Value is 15x higher than average"
    },
    {
      "type": "missing_value",
      "sheet_name": "Q1",
      "column": "Product",
      "row": 23,
      "message": "Empty cell in required column"
    }
  ],
  "total_anomalies": 5
}
```

### Get Usage Summary
```http
GET /api/v1/usage/summary
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "period": "2024-01",
  "total_queries": 1250,
  "total_files_scanned": 45,
  "total_rows_processed": 125000,
  "estimated_cost": 12.50,
  "cache_hit_rate": 0.35,
  "average_processing_time_ms": 1150
}
```

---

## 12. Traceability (NEW)

### Get Query Trace
```http
GET /api/v1/query/trace/{trace_id}
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "trace_id": "tr_abc123",
  "query_text": "What was the total revenue in Q1 2024?",
  "timestamp": "2024-01-15T10:00:00Z",
  "user_id": "girish",
  "session_id": "session_123",
  "file_selection": {
    "candidates": [
      {
        "file_id": "file_123",
        "file_name": "sales_2024.xlsx",
        "semantic_score": 0.92,
        "metadata_score": 0.88,
        "preference_score": 0.75,
        "combined_score": 0.89
      }
    ],
    "selected_file_id": "file_123",
    "reasoning": "Highest combined score with strong semantic match",
    "confidence": 0.96
  },
  "sheet_selection": {
    "candidates": [
      {
        "sheet_name": "Q1",
        "name_score": 0.95,
        "header_score": 0.90,
        "combined_score": 0.92
      }
    ],
    "selected_sheets": ["Q1"],
    "reasoning": "Sheet name matches query temporal reference",
    "confidence": 0.94
  },
  "query_classification": {
    "query_type": "aggregation",
    "confidence": 0.98
  },
  "answer": {
    "text": "The total revenue in Q1 2024 was $1,234,567",
    "confidence": 0.95
  },
  "performance": {
    "total_processing_time_ms": 1250,
    "file_selection_time_ms": 150,
    "sheet_selection_time_ms": 80,
    "retrieval_time_ms": 200,
    "generation_time_ms": 820
  }
}
```

### Get Data Lineage
```http
GET /api/v1/lineage/{lineage_id}
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "lineage_id": "lin_abc123",
  "answer_component": "The total revenue in Q1 2024 was $1,234,567",
  "source": {
    "file_id": "file_123",
    "file_name": "sales_2024.xlsx",
    "sheet_name": "Q1",
    "cell_range": "B2:B100",
    "source_value": "SUM of Revenue column"
  },
  "processing_path": {
    "chunk_id": "chunk_045",
    "embedding_id": "emb_xyz789",
    "retrieval_score": 0.94
  },
  "timestamps": {
    "indexed_at": "2024-01-10T08:00:00Z",
    "last_verified_at": "2024-01-15T10:00:00Z"
  },
  "is_stale": false,
  "stale_reason": null
}
```

---

## Error Responses

All endpoints may return these common error responses:

### 401 Unauthorized
```json
{
  "detail": "Invalid or expired token"
}
```

### 403 Forbidden
```json
{
  "detail": "Access denied to resource"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 422 Validation Error
```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "details": {
    "errors": [
      {
        "loc": ["body", "query"],
        "msg": "field required",
        "type": "value_error.missing"
      }
    ]
  },
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 500 Internal Server Error
```json
{
  "error": "InternalServerError",
  "message": "An internal error occurred",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
