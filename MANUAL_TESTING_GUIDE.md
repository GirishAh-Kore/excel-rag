# Manual Testing Guide for Docker Deployment

This guide walks you through deploying the application in Docker and manually testing all functionality.

## Prerequisites

Before starting, ensure you have:
- Docker Engine 20.10+ installed
- Docker Compose 2.0+ installed
- Google Cloud OAuth credentials (for Google Drive integration)
- OpenAI API key (or Anthropic API key)
- 4GB+ RAM available
- 10GB+ disk space

## Step 1: Initial Setup

### 1.1 Create Environment File

```bash
# Copy the example environment file
cp .env.docker.example .env
```

### 1.2 Configure Required Credentials

Edit the `.env` file and add your credentials:

```bash
# Open in your editor
nano .env
# or
vim .env
# or
code .env
```

**Minimum Required Configuration:**

```bash
# Google Drive OAuth (get from https://console.cloud.google.com/)
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback

# OpenAI API Key (get from https://platform.openai.com/api-keys)
OPENAI_API_KEY=sk-your-openai-key-here
EMBEDDING_API_KEY=sk-your-openai-key-here
LLM_API_KEY=sk-your-openai-key-here

# Web Authentication (change these!)
WEB_AUTH_USERNAME=girish
WEB_AUTH_PASSWORD=Girish@123

# Security Keys (generate new ones!)
JWT_SECRET_KEY=your-jwt-secret-key-here
TOKEN_ENCRYPTION_KEY=your-32-character-encryption-key
```

**Generate Secure Keys:**

```bash
# Generate JWT secret key
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate encryption key (must be 32 characters)
python3 -c "import secrets; print('TOKEN_ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```

Copy the generated keys into your `.env` file.

### 1.3 Build Frontend (First Time Only)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Build the frontend
npm run build

# Return to root directory
cd ..
```

## Step 2: Deploy with Docker

### 2.1 Build and Start Services

```bash
# Build and start all services in detached mode
docker-compose up -d --build
```

This will:
- Build the application Docker image (takes 5-10 minutes first time)
- Pull the ChromaDB image
- Create Docker volumes for data persistence
- Start the web application and ChromaDB services

### 2.2 Monitor Startup

Watch the logs to ensure everything starts correctly:

```bash
# Follow logs from all services
docker-compose logs -f

# Or watch specific service
docker-compose logs -f web
```

Look for these success messages:
- `Application startup complete`
- `Uvicorn running on http://0.0.0.0:8000`
- `ChromaDB server started`

Press `Ctrl+C` to stop following logs (services keep running).

### 2.3 Verify Services are Running

```bash
# Check service status
docker-compose ps
```

Expected output:
```
NAME                COMMAND                  SERVICE   STATUS    PORTS
web                 "gunicorn..."            web       running   0.0.0.0:8000->8000/tcp
chromadb            "uvicorn..."             chromadb  running   0.0.0.0:8001->8000/tcp
```

### 2.4 Check Application Health

```bash
# Test health endpoint
curl http://localhost:8000/health

# Or use httpie if installed
http http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-11-29T...",
  "environment": "production",
  "components": {
    "authentication": "not_authenticated",
    "vector_store": "chromadb",
    "embedding_service": "openai",
    "llm_service": "openai",
    "cache_service": "memory"
  }
}
```

## Step 3: Manual Testing - Web Interface

### 3.1 Access the Application

Open your browser and navigate to:
```
http://localhost:8000
```

You should see the login page.

### 3.2 Test Authentication (Task 23.1)

#### Test 1: Login with Correct Credentials
1. Enter username: `girish` (or your configured username)
2. Enter password: `Girish@123` (or your configured password)
3. Click "Login"
4. ✅ **Expected**: Successfully logged in, redirected to configuration page

#### Test 2: Login with Incorrect Credentials
1. Logout if logged in
2. Enter username: `wrong_user`
3. Enter password: `wrong_password`
4. Click "Login"
5. ✅ **Expected**: Error message "Invalid username or password"

#### Test 3: Session Persistence
1. Login successfully
2. Refresh the page (F5 or Cmd+R)
3. ✅ **Expected**: Still logged in, not redirected to login page

#### Test 4: Logout
1. While logged in, click "Logout" button
2. ✅ **Expected**: Redirected to login page
3. Try to access protected pages directly
4. ✅ **Expected**: Redirected back to login page

### 3.3 Test File Upload (Task 23.2)

#### Test 1: Upload Valid Excel File
1. Login to the application
2. Navigate to "Configuration" or "Files" page
3. Click "Upload Files" or drag-and-drop area
4. Select a valid Excel file (.xlsx, .xls, or .xlsm)
5. ✅ **Expected**: 
   - Upload progress bar appears
   - File appears in the file list
   - Status shows "Indexing" or "Indexed"

#### Test 2: Upload Invalid File Type
1. Try to upload a non-Excel file (e.g., .txt, .pdf, .docx)
2. ✅ **Expected**: Error message "Invalid file type. Allowed types: .xlsx, .xls, .xlsm"

#### Test 3: File List Display
1. Navigate to the files list page
2. ✅ **Expected**:
   - All uploaded files are displayed
   - Each file shows: name, size, upload date, status
   - Pagination controls appear if more than 20 files

#### Test 4: File List Pagination
1. If you have more than 20 files, test pagination
2. Click "Next" or page numbers
3. ✅ **Expected**: Different files displayed on each page

#### Test 5: Delete File
1. Find a file in the list
2. Click "Delete" button
3. Confirm deletion
4. ✅ **Expected**: File removed from list and disk

#### Test 6: Re-index File
1. Find a file in the list
2. Click "Re-index" button
3. ✅ **Expected**: Status changes to "Indexing", then "Indexed"

### 3.4 Test Google Drive Integration (Task 23.3)

#### Test 1: Connect Google Drive
1. Navigate to "Configuration" page
2. Click "Connect Google Drive"
3. ✅ **Expected**: Redirected to Google OAuth consent screen
4. Authorize the application
5. ✅ **Expected**: Redirected back, connection status shows "Connected"

#### Test 2: View Connection Status
1. After connecting, check the connection status
2. ✅ **Expected**: Shows connected email address and connection time

#### Test 3: Index Files from Google Drive
1. With Google Drive connected, click "Index Google Drive Files"
2. ✅ **Expected**: 
   - Indexing starts
   - Progress indicator appears
   - Files from Google Drive appear in file list

#### Test 4: Disconnect Google Drive
1. Click "Disconnect" button
2. ✅ **Expected**: 
   - Connection status changes to "Not Connected"
   - Token is revoked

### 3.5 Test Chat Functionality (Task 23.4)

#### Test 1: Submit Query
1. Navigate to "Chat" page
2. Type a question about your data (e.g., "What is the total revenue?")
3. Click "Send" or press Enter
4. ✅ **Expected**:
   - Loading indicator appears
   - Answer is displayed
   - Source citations are shown
   - Confidence score is displayed

#### Test 2: View Source Citations
1. After receiving an answer, look for source citations
2. Click on a citation to expand
3. ✅ **Expected**: Shows file name, sheet name, and relevant data

#### Test 3: View Confidence Score
1. Check the confidence score badge on the answer
2. ✅ **Expected**: Shows percentage (e.g., "85% confident")

#### Test 4: Conversation History
1. Submit multiple queries in the same session
2. Scroll up to see previous messages
3. ✅ **Expected**: All messages are preserved in order

#### Test 5: New Conversation
1. Click "New Conversation" button
2. ✅ **Expected**: 
   - Chat area clears
   - New conversation starts
   - Previous conversation saved in sidebar

#### Test 6: Delete Conversation
1. Find a conversation in the sidebar
2. Click delete icon
3. ✅ **Expected**: Conversation removed from list

#### Test 7: Follow-up Questions
1. Ask an initial question
2. Ask a follow-up that references the previous answer
3. ✅ **Expected**: System understands context and provides relevant answer

## Step 4: Manual Testing - API Endpoints

### 4.1 Test Authentication API

```bash
# Test login
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "girish", "password": "Girish@123"}'

# Save the token from response
TOKEN="your-token-here"

# Test status
curl http://localhost:8000/api/auth/status \
  -H "Authorization: Bearer $TOKEN"

# Test logout
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer $TOKEN"
```

### 4.2 Test File Management API

```bash
# List files
curl http://localhost:8000/api/files/list \
  -H "Authorization: Bearer $TOKEN"

# Upload file
curl -X POST http://localhost:8000/api/files/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/your/file.xlsx"

# Delete file
curl -X DELETE http://localhost:8000/api/files/{file_id} \
  -H "Authorization: Bearer $TOKEN"
```

### 4.3 Test Chat API

```bash
# Submit query
curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the total revenue?", "session_id": "test-session"}'

# List sessions
curl http://localhost:8000/api/chat/sessions \
  -H "Authorization: Bearer $TOKEN"
```

## Step 5: Test Docker Deployment Features (Task 23.5)

### 5.1 Test Data Persistence

```bash
# Stop containers
docker-compose down

# Start containers again
docker-compose up -d

# Check if data persists
curl http://localhost:8000/api/files/list \
  -H "Authorization: Bearer $TOKEN"
```

✅ **Expected**: Previously uploaded files still appear

### 5.2 Test Environment Variables

```bash
# Edit .env file and change a setting
nano .env

# Restart services
docker-compose restart

# Verify change took effect
curl http://localhost:8000/health
```

### 5.3 Test Health Checks

```bash
# Check container health
docker-compose ps

# Check application health endpoint
curl http://localhost:8000/health

# Check metrics endpoint
curl http://localhost:8000/api/v1/metrics
```

### 5.4 Test Backup and Restore

```bash
# Create backup
./scripts/docker-backup.sh

# List backups
ls -lh backups/

# Stop services
docker-compose down -v

# Restore from backup
./scripts/docker-restore.sh backups/backup-YYYYMMDD-HHMMSS.tar.gz

# Start services
docker-compose up -d

# Verify data restored
curl http://localhost:8000/api/files/list \
  -H "Authorization: Bearer $TOKEN"
```

## Step 6: Monitor and Debug

### 6.1 View Logs

```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View logs for specific service
docker-compose logs web
docker-compose logs chromadb

# View last 100 lines
docker-compose logs --tail=100

# View logs with timestamps
docker-compose logs -t
```

### 6.2 Check Resource Usage

```bash
# View container stats
docker stats

# View disk usage
docker system df

# View volume usage
docker volume ls
```

### 6.3 Access Container Shell

```bash
# Access web container
docker-compose exec web bash

# Inside container, you can:
# - Check files: ls -la
# - View logs: cat /app/logs/app.log
# - Check environment: env
# - Test connectivity: curl http://chromadb:8000

# Exit container
exit
```

### 6.4 Inspect Volumes

```bash
# List volumes
docker volume ls

# Inspect specific volume
docker volume inspect kiro-answerFromExcel_app-data

# View volume contents
docker run --rm -v kiro-answerFromExcel_app-data:/data alpine ls -la /data
```

## Step 7: Performance Testing

### 7.1 Test Upload Performance

```bash
# Upload multiple files
for i in {1..5}; do
  curl -X POST http://localhost:8000/api/files/upload \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@test-file-$i.xlsx" &
done
wait

# Check indexing status
curl http://localhost:8000/api/files/indexing-status \
  -H "Authorization: Bearer $TOKEN"
```

### 7.2 Test Query Performance

```bash
# Time a query
time curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the total revenue?", "session_id": "perf-test"}'
```

### 7.3 Test Concurrent Users

```bash
# Install Apache Bench if not available
# brew install httpd (macOS)
# apt-get install apache2-utils (Ubuntu)

# Test with 10 concurrent users, 100 requests
ab -n 100 -c 10 -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/files/list
```

## Step 8: Cleanup

### 8.1 Stop Services

```bash
# Stop services (keeps data)
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

### 8.2 Remove Images

```bash
# Remove application image
docker rmi kiro-answerFromExcel-web

# Remove all unused images
docker image prune -a
```

### 8.3 Clean Up System

```bash
# Remove all stopped containers, unused networks, dangling images
docker system prune

# Remove everything including volumes
docker system prune -a --volumes
```

## Troubleshooting

### Issue: Port 8000 Already in Use

**Solution**: Change the port in `docker-compose.yml`:
```yaml
services:
  web:
    ports:
      - "8080:8000"  # Change 8080 to any available port
```

### Issue: Out of Memory

**Solution**: Increase Docker memory allocation:
- Docker Desktop: Settings → Resources → Memory (set to 4GB+)

### Issue: Services Won't Start

**Solution**: Check logs and rebuild:
```bash
docker-compose logs
docker-compose down
docker-compose up -d --build
```

### Issue: Can't Connect to ChromaDB

**Solution**: Verify ChromaDB is running:
```bash
docker-compose ps chromadb
curl http://localhost:8001/api/v1/heartbeat
```

### Issue: Frontend Not Loading

**Solution**: Rebuild frontend:
```bash
cd frontend
npm run build
cd ..
docker-compose up -d --build
```

## Test Checklist

Use this checklist to track your testing progress:

### Authentication (Task 23.1)
- [ ] Login with correct credentials
- [ ] Login with incorrect credentials
- [ ] Session persistence across page refreshes
- [ ] Logout functionality
- [ ] Protected route access without authentication

### File Management (Task 23.2)
- [ ] Single file upload with progress tracking
- [ ] Multiple file upload
- [ ] File type validation (accept .xlsx, .xls, .xlsm)
- [ ] File type validation (reject other types)
- [ ] File size validation
- [ ] File list display with pagination
- [ ] File deletion
- [ ] File re-indexing

### Google Drive Integration (Task 23.3)
- [ ] OAuth connection flow
- [ ] Connection status display
- [ ] File indexing from Google Drive
- [ ] Disconnection and token revocation

### Chat Functionality (Task 23.4)
- [ ] Query submission and response display
- [ ] Source citations display
- [ ] Confidence score display
- [ ] Conversation history
- [ ] New conversation creation
- [ ] Conversation deletion
- [ ] Follow-up questions with context

### Docker Deployment (Task 23.5)
- [ ] Building Docker images
- [ ] Starting services with docker-compose
- [ ] Accessing web application from browser
- [ ] Data persistence across container restarts
- [ ] Environment variable configuration
- [ ] Health checks and monitoring

## Summary

You've now deployed and tested the application in Docker! The application should be:
- ✅ Running in Docker containers
- ✅ Accessible at http://localhost:8000
- ✅ Persisting data across restarts
- ✅ Fully functional for authentication, file management, and chat

For production deployment, review the security recommendations in `DOCKER.md` and set up proper monitoring, backups, and HTTPS.

## Next Steps

1. **Production Deployment**: Follow `DOCKER.md` for production setup
2. **Monitoring**: Set up logging and monitoring tools
3. **Backups**: Configure automated backups with cron
4. **Security**: Review and implement security best practices
5. **Scaling**: Consider using Kubernetes for larger deployments

## Support

- **Documentation**: See `DOCKER.md` for detailed information
- **Quick Start**: See `DOCKER_QUICK_START.md` for fast setup
- **Test Results**: See `DOCKER_TEST_RESULTS.md` for automated test results
- **API Reference**: See `API_ENDPOINTS_REFERENCE.md` for API documentation
