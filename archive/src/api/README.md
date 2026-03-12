# Google Drive Excel RAG API

REST API for the Google Drive Excel RAG system. Provides endpoints for authentication, indexing, and querying Excel files stored in Google Drive.

## Quick Start

### 1. Start the Server

```bash
# Development mode with auto-reload
python -m uvicorn src.main:app --reload

# Production mode
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

### 2. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### 3. Check Health

```bash
curl http://localhost:8000/health
```

## API Endpoints

### Base URL
- Development: `http://localhost:8000/api/v1`
- Production: `https://your-domain.com/api/v1`

### Authentication (`/auth`)

#### POST `/auth/login`
Initiate OAuth 2.0 flow with Google.

**Response:**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "random-state-string"
}
```

#### GET `/auth/callback`
Handle OAuth callback (called by Google after user grants permissions).

**Query Parameters:**
- `code`: Authorization code
- `state`: State parameter for CSRF validation

#### POST `/auth/logout`
Revoke access and clear stored credentials.

#### GET `/auth/status`
Check authentication status.

**Response:**
```json
{
  "authenticated": true,
  "token_expiry": "2024-01-15T10:30:00Z",
  "user_email": "user@example.com"
}
```

### Indexing (`/index`)

#### POST `/index/full`
Start full indexing of all Excel files.

**Request Body:**
```json
{
  "folder_id": "optional-folder-id",
  "file_filters": ["*.xlsx"],
  "force_reindex": false
}
```

**Response:**
```json
{
  "job_id": "uuid",
  "status": "running",
  "message": "Full indexing started successfully"
}
```

#### POST `/index/incremental`
Index only changed files since last indexing.

**Request Body:**
```json
{
  "folder_id": "optional-folder-id",
  "file_filters": ["*.xlsx"]
}
```

#### GET `/index/status/{job_id}`
Get current status of indexing job.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "running",
  "progress_percentage": 45.5,
  "current_file": "expenses_jan.xlsx",
  "files_processed": 10,
  "files_total": 22,
  "started_at": "2024-01-15T10:00:00Z",
  "estimated_completion": "2024-01-15T10:15:00Z"
}
```

#### GET `/index/report/{job_id}`
Get detailed report of completed indexing job.

**Response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "files_processed": 22,
  "files_failed": 1,
  "files_skipped": 3,
  "sheets_indexed": 45,
  "embeddings_generated": 180,
  "duration_seconds": 125.5,
  "started_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:02:05Z",
  "errors": ["Error processing file.xlsx: corrupted"]
}
```

#### POST `/index/pause/{job_id}`
Pause a running indexing job.

#### POST `/index/resume/{job_id}`
Resume a paused indexing job.

#### POST `/index/stop/{job_id}`
Stop an indexing job (cannot be resumed).

#### WebSocket `/index/ws/{job_id}`
Real-time progress updates for indexing job.

**Message Format:**
```json
{
  "job_id": "uuid",
  "status": "running",
  "progress_percentage": 45.5,
  "current_file": "expenses_jan.xlsx",
  "files_processed": 10,
  "files_total": 22
}
```

### Query (`/query`)

#### POST `/query`
Submit a natural language query.

**Request Body:**
```json
{
  "query": "What is the total expense in January 2024?",
  "session_id": "optional-session-id",
  "language": "en"
}
```

**Response:**
```json
{
  "answer": "The total expense in January 2024 is $15,234.50",
  "sources": [
    {
      "file_name": "expenses_jan_2024.xlsx",
      "file_path": "/Finance/2024/expenses_jan_2024.xlsx",
      "sheet_name": "Summary",
      "cell_range": "B10",
      "citation_text": "Source: expenses_jan_2024.xlsx, Sheet: Summary, Cell: B10"
    }
  ],
  "confidence": 95.5,
  "session_id": "uuid",
  "requires_clarification": false,
  "query_language": "en",
  "processing_time_ms": 1234.5
}
```

**Response with Clarification:**
```json
{
  "answer": null,
  "sources": [],
  "confidence": 65.0,
  "session_id": "uuid",
  "requires_clarification": true,
  "clarification_question": "I found multiple expense files. Which one would you like?",
  "clarification_options": [
    {
      "option_id": "1",
      "description": "expenses_jan_2024.xlsx (modified: 2024-01-15)",
      "file_name": "expenses_jan_2024.xlsx",
      "confidence": 0.85
    },
    {
      "option_id": "2",
      "description": "expenses_january.xlsx (modified: 2024-01-10)",
      "file_name": "expenses_january.xlsx",
      "confidence": 0.75
    }
  ],
  "query_language": "en",
  "processing_time_ms": 856.2
}
```

#### POST `/query/clarify`
Respond to clarification question.

**Request Body:**
```json
{
  "session_id": "uuid",
  "selected_option_id": "1"
}
```

#### GET `/query/history`
Get query history with pagination.

**Query Parameters:**
- `limit`: Maximum number of queries (default: 10, max: 100)
- `offset`: Number of queries to skip (default: 0)
- `session_id`: Filter by session ID (optional)

**Response:**
```json
{
  "queries": [
    {
      "query_id": "uuid",
      "query": "What is the total expense?",
      "answer": "The total expense is $15,234.50",
      "confidence": 95.5,
      "timestamp": "2024-01-15T10:30:00Z",
      "session_id": "uuid"
    }
  ],
  "total": 25,
  "limit": 10,
  "offset": 0
}
```

#### DELETE `/query/history`
Clear query history.

**Query Parameters:**
- `session_id`: Clear specific session (optional, clears all if not provided)

#### GET `/query/session/{session_id}`
Get session context and history.

**Response:**
```json
{
  "session_id": "uuid",
  "queries": [...],
  "selected_files": ["expenses_jan_2024.xlsx", "revenue_jan_2024.xlsx"],
  "created_at": "2024-01-15T10:00:00Z",
  "last_activity": "2024-01-15T10:30:00Z"
}
```

#### POST `/query/feedback`
Submit feedback on query results.

**Request Body:**
```json
{
  "query_id": "uuid",
  "helpful": true,
  "selected_file": "expenses_jan_2024.xlsx",
  "comments": "Perfect answer!"
}
```

## Rate Limits

- **Query endpoints**: 10 requests/minute
- **Indexing endpoints**: 1 request/minute
- **Other endpoints**: 60 requests/minute

Rate limit headers are included in responses:
- `X-RateLimit-Limit`: Maximum requests allowed
- `X-RateLimit-Remaining`: Remaining requests in current window

## Error Handling

All errors return a structured error response:

```json
{
  "error": "ValidationError",
  "message": "Request validation failed",
  "details": {
    "errors": [...]
  },
  "correlation_id": "uuid",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request (validation error)
- `401`: Unauthorized (authentication required)
- `403`: Forbidden (access denied)
- `404`: Not Found (resource not found)
- `422`: Unprocessable Entity (validation error)
- `429`: Too Many Requests (rate limit exceeded)
- `500`: Internal Server Error
- `502`: Bad Gateway (external service error)

## Correlation IDs

Every request is assigned a unique correlation ID for tracing:
- Automatically generated if not provided
- Can be provided via `X-Correlation-ID` header
- Returned in response headers and error responses
- Used for logging and debugging

## Authentication

Protected endpoints require authentication:
1. Call `/auth/login` to get authorization URL
2. User visits URL and grants permissions
3. Google redirects to `/auth/callback`
4. Subsequent requests are authenticated

## Python Client

Use the provided Python client for easy API interaction:

```python
from examples.api_usage import RAGAPIClient

client = RAGAPIClient("http://localhost:8000")

# Check health
health = client.health_check()
print(health)

# Authenticate
client.login()  # Follow the URL to grant permissions

# Start indexing
result = client.start_full_indexing()
job_id = result['job_id']

# Wait for completion
report = client.wait_for_indexing(job_id)
print(f"Indexed {report['sheets_indexed']} sheets")

# Query
result = client.query("What is the total expense?")
print(result['answer'])
```

## WebSocket Example

```javascript
// Connect to indexing progress WebSocket
const ws = new WebSocket('ws://localhost:8000/api/v1/index/ws/job-id');

ws.onopen = () => {
  console.log('Connected to indexing progress');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`Progress: ${data.progress_percentage}%`);
  console.log(`Current file: ${data.current_file}`);
  
  if (data.status === 'completed') {
    console.log('Indexing completed!');
    ws.close();
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('WebSocket closed');
};
```

## Configuration

Configure the API via environment variables:

```bash
# API Server
API_HOST=0.0.0.0
API_PORT=8000
API_RATE_LIMIT=100
CORS_ORIGINS=http://localhost:3000,https://app.example.com

# Environment
APP_ENV=development  # or production
LOG_LEVEL=INFO

# See .env.example for full configuration
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/

# Run API tests only
pytest tests/test_api_*.py

# Run with coverage
pytest --cov=src/api tests/
```

### API Documentation

The API is self-documenting using OpenAPI/Swagger:
- Visit `/docs` for interactive documentation
- Visit `/redoc` for alternative documentation
- Download `/openapi.json` for OpenAPI specification

### Adding New Endpoints

1. Create endpoint in appropriate router (`auth.py`, `indexing.py`, `query.py`)
2. Define request/response models in `models.py`
3. Add dependencies in `dependencies.py` if needed
4. Update this README with endpoint documentation
5. Add tests in `tests/test_api_*.py`

## Production Deployment

### Recommendations

1. **Use HTTPS**: Enable SSL/TLS in production
2. **Set CORS origins**: Configure allowed origins in `CORS_ORIGINS`
3. **Use Redis**: Replace in-memory storage with Redis for job tracking
4. **Enable monitoring**: Add Prometheus metrics endpoint
5. **Use reverse proxy**: Deploy behind nginx or similar
6. **Set rate limits**: Adjust rate limits based on usage
7. **Enable logging**: Configure structured logging with ELK stack

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
      - GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
      - LLM_API_KEY=${LLM_API_KEY}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
    volumes:
      - ./data:/app/data
      - ./tokens:/app/tokens
```

## Support

For issues or questions:
1. Check the API documentation at `/docs`
2. Review error messages and correlation IDs
3. Check logs for detailed error information
4. Refer to the main README for setup instructions

## License

See main project LICENSE file.
