# API Endpoints Reference for Frontend

## Base URL

- Development: `http://localhost:8000`
- Production: Configure as needed

## Authentication

All endpoints except `/api/auth/login` require authentication via JWT token in the `Authorization` header:

```
Authorization: Bearer <token>
```

## Endpoints

### 1. Web Authentication

#### Login
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

**Error (401 Unauthorized):**
```json
{
  "detail": "Invalid username or password"
}
```

#### Logout
```http
POST /api/auth/logout
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Logged out successfully"
}
```

#### Check Status
```http
GET /api/auth/status
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "authenticated": true,
  "username": "girish",
  "expires_at": "2024-01-15T10:30:00"
}
```

---

### 2. File Management

#### Upload File
```http
POST /api/files/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <Excel file>
```

**Response (200 OK):**
```json
{
  "file_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "expenses.xlsx",
  "size": 1048576,
  "status": "indexing",
  "message": "File uploaded and indexing started",
  "indexing_job_id": "job_123456"
}
```

**Error (400 Bad Request):**
```json
{
  "detail": "Invalid file type. Allowed types: .xlsx, .xls, .xlsm"
}
```

**Error (413 Request Entity Too Large):**
```json
{
  "detail": "File too large. Maximum size: 100MB"
}
```

#### List Files
```http
GET /api/files/list?page=1&page_size=20
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "files": [
    {
      "file_id": "550e8400-e29b-41d4-a716-446655440000",
      "filename": "expenses.xlsx",
      "file_path": "/uploads/550e8400_expenses.xlsx",
      "size": 1048576,
      "uploaded_at": "2024-01-15T10:00:00",
      "indexed_at": "2024-01-15T10:05:00",
      "status": "indexed",
      "sheets_count": 3
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 20
}
```

#### Delete File
```http
DELETE /api/files/{file_id}
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "File deleted successfully",
  "file_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error (404 Not Found):**
```json
{
  "detail": "File not found: 550e8400-e29b-41d4-a716-446655440000"
}
```

#### Reindex File
```http
POST /api/files/{file_id}/reindex
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Re-indexing started",
  "job_id": "job_789012"
}
```

#### Get Indexing Status
```http
GET /api/files/indexing-status
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "active_jobs": [
    {
      "job_id": "job_123456",
      "status": "running",
      "progress": 45.5,
      "current_file": "expenses.xlsx"
    }
  ],
  "completed_jobs": [
    {
      "job_id": "job_789012",
      "status": "completed",
      "files_processed": 5
    }
  ],
  "failed_jobs": []
}
```

---

### 3. Google Drive Configuration

#### Connect to Google Drive
```http
POST /api/config/gdrive/connect
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "random_state_string",
  "message": "Please authorize access to Google Drive"
}
```

**Frontend Action:** Redirect user to `authorization_url`

#### OAuth Callback
```http
GET /api/config/gdrive/callback?code=<auth_code>&state=<state>
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Google Drive connected successfully",
  "user_email": "authenticated"
}
```

**Error (400 Bad Request):**
```json
{
  "detail": "OAuth callback failed. Invalid code or state."
}
```

#### Disconnect Google Drive
```http
DELETE /api/config/gdrive/disconnect
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Google Drive disconnected successfully"
}
```

#### Check Connection Status
```http
GET /api/config/gdrive/status
Authorization: Bearer <token>
```

**Response (200 OK - Connected):**
```json
{
  "connected": true,
  "user_email": "user@example.com",
  "token_expiry": "2024-01-15T12:00:00",
  "scopes": [
    "https://www.googleapis.com/auth/drive.readonly"
  ]
}
```

**Response (200 OK - Not Connected):**
```json
{
  "connected": false,
  "user_email": null,
  "token_expiry": null,
  "scopes": null
}
```

---

### 4. Chat Sessions

#### Submit Query
```http
POST /api/chat/query
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "What is the total expense in January?",
  "session_id": "session_123"  // Optional, auto-generated if not provided
}
```

**Response (200 OK):**
```json
{
  "answer": "The total expense in January is $15,234.50",
  "sources": [
    {
      "file_name": "expenses_jan2024.xlsx",
      "file_path": "/uploads/expenses_jan2024.xlsx",
      "sheet_name": "Summary",
      "cell_range": "B10",
      "citation_text": "Source: expenses_jan2024.xlsx, Sheet: Summary, Cell: B10"
    }
  ],
  "confidence": 95.5,
  "session_id": "session_123",
  "requires_clarification": false,
  "clarification_question": null,
  "clarification_options": [],
  "processing_time_ms": 1234.56,
  "timestamp": "2024-01-15T10:30:00"
}
```

**Response with Clarification:**
```json
{
  "answer": null,
  "sources": [],
  "confidence": 65.0,
  "session_id": "session_123",
  "requires_clarification": true,
  "clarification_question": "Which file did you mean?",
  "clarification_options": [
    {
      "option_id": "opt_1",
      "description": "expenses_jan2024.xlsx",
      "file_name": "expenses_jan2024.xlsx",
      "confidence": 0.7
    },
    {
      "option_id": "opt_2",
      "description": "expenses_feb2024.xlsx",
      "file_name": "expenses_feb2024.xlsx",
      "confidence": 0.6
    }
  ],
  "processing_time_ms": 890.12,
  "timestamp": "2024-01-15T10:30:00"
}
```

#### List Sessions
```http
GET /api/chat/sessions
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "sessions": [
    {
      "session_id": "session_123",
      "created_at": "2024-01-15T10:00:00",
      "last_activity": "2024-01-15T10:30:00",
      "query_count": 5
    }
  ],
  "total": 3
}
```

#### Create Session
```http
POST /api/chat/sessions
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "session_id": "session_456",
  "created_at": "2024-01-15T10:35:00",
  "message": "Session created successfully"
}
```

#### Delete Session
```http
DELETE /api/chat/sessions/{session_id}
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Session deleted successfully",
  "session_id": "session_123"
}
```

**Error (404 Not Found):**
```json
{
  "detail": "Session not found: session_123"
}
```

#### Get Session History
```http
GET /api/chat/sessions/{session_id}/history
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "session_id": "session_123",
  "messages": [
    {
      "message_id": "msg_1",
      "role": "user",
      "content": "What is the total expense?",
      "timestamp": "2024-01-15T10:00:00",
      "sources": [],
      "confidence": null
    },
    {
      "message_id": "msg_2",
      "role": "assistant",
      "content": "The total expense is $15,234.50",
      "timestamp": "2024-01-15T10:00:05",
      "sources": [
        {
          "file_name": "expenses.xlsx",
          "file_path": "/uploads/expenses.xlsx",
          "sheet_name": "Summary",
          "cell_range": "B10",
          "citation_text": "Source: expenses.xlsx, Sheet: Summary, Cell: B10"
        }
      ],
      "confidence": 95.5
    }
  ],
  "created_at": "2024-01-15T10:00:00",
  "last_activity": "2024-01-15T10:30:00"
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
  "timestamp": "2024-01-15T10:30:00"
}
```

### 500 Internal Server Error
```json
{
  "error": "InternalServerError",
  "message": "An internal error occurred",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00"
}
```

---

## Frontend Integration Examples

### React/TypeScript Example

```typescript
// authService.ts
const API_BASE_URL = 'http://localhost:8000';

export const login = async (username: string, password: string) => {
  const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  });
  
  if (!response.ok) {
    throw new Error('Login failed');
  }
  
  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  return data;
};

export const getAuthHeader = () => {
  const token = localStorage.getItem('token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

// fileService.ts
export const uploadFile = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch(`${API_BASE_URL}/api/files/upload`, {
    method: 'POST',
    headers: getAuthHeader(),
    body: formData,
  });
  
  if (!response.ok) {
    throw new Error('Upload failed');
  }
  
  return response.json();
};

// chatService.ts
export const submitQuery = async (query: string, sessionId?: string) => {
  const response = await fetch(`${API_BASE_URL}/api/chat/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
    },
    body: JSON.stringify({ query, session_id: sessionId }),
  });
  
  if (!response.ok) {
    throw new Error('Query failed');
  }
  
  return response.json();
};
```

---

## Testing with cURL

### Login and Get Token
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"girish","password":"Girish@123"}' \
  | jq -r '.access_token')

echo $TOKEN
```

### Upload File
```bash
curl -X POST http://localhost:8000/api/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@expenses.xlsx"
```

### Submit Query
```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the total expense?"}'
```

---

## API Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

These provide interactive testing and detailed schema information.
