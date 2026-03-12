# Docker Deployment Guide

This guide covers deploying the Google Drive Excel RAG System using Docker and Docker Compose.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Building and Running](#building-and-running)
- [Accessing the Application](#accessing-the-application)
- [Data Persistence](#data-persistence)
- [Monitoring and Logs](#monitoring-and-logs)
- [Backup and Restore](#backup-and-restore)
- [Troubleshooting](#troubleshooting)
- [Production Deployment](#production-deployment)
- [Useful Commands](#useful-commands)

## Prerequisites

- Docker Engine 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose 2.0+ ([Install Docker Compose](https://docs.docker.com/compose/install/))
- At least 4GB RAM available for Docker
- At least 10GB disk space for images and volumes

Verify installation:
```bash
docker --version
docker-compose --version
```

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd gdrive-excel-rag
```

### 2. Configure Environment Variables

Copy the Docker environment template:
```bash
cp .env.docker.example .env
```

Edit `.env` and fill in required values:
```bash
# Required: Google Drive OAuth credentials
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Required: OpenAI API key (or other LLM provider)
EMBEDDING_API_KEY=your_openai_api_key_here
LLM_API_KEY=your_openai_api_key_here

# Required: Security keys (generate with provided commands)
JWT_SECRET_KEY=your_jwt_secret_key_here
TOKEN_ENCRYPTION_KEY=your_32_character_encryption_key_here
```

Generate secure keys:
```bash
# Generate JWT secret
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# Generate encryption key
python -c "import secrets; print('TOKEN_ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
```

### 3. Build Frontend

Before building Docker images, build the frontend:
```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Build and Start Services

```bash
docker-compose up -d
```

This will:
- Build the application Docker image
- Pull the ChromaDB image
- Create necessary volumes
- Start all services

### 5. Verify Deployment

Check service health:
```bash
docker-compose ps
```

All services should show "healthy" status.

Access the application:
- Web UI: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- ChromaDB: http://localhost:8001

## Configuration

### Environment Variables

The `.env` file contains all configuration. Key sections:

#### Google Drive OAuth
```bash
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/v1/auth/callback
```

#### LLM and Embedding Services
```bash
# OpenAI (default)
EMBEDDING_PROVIDER=openai
EMBEDDING_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small

LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4

# Or use Anthropic Claude
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-sonnet-20241022
```

#### Web Authentication
```bash
WEB_AUTH_USERNAME=girish
WEB_AUTH_PASSWORD=Girish@123  # Change this!
```

#### File Upload Limits
```bash
MAX_UPLOAD_SIZE_MB=100
```

#### Language Support
```bash
SUPPORTED_LANGUAGES=en,th
DEFAULT_LANGUAGE=en
ENABLE_LEMMATIZATION=true
THAI_TOKENIZER_ENGINE=newmm
```

### Docker Compose Configuration

The `docker-compose.yml` defines two services:

1. **web**: Main application (FastAPI + React frontend)
   - Port: 8000
   - Volumes: app-data, uploads, logs, tokens, chroma-data
   
2. **chromadb**: Vector database
   - Port: 8001
   - Volume: chroma-data

## Building and Running

### Build Images

Build without cache (clean build):
```bash
docker-compose build --no-cache
```

Build with cache (faster):
```bash
docker-compose build
```

### Start Services

Start in detached mode (background):
```bash
docker-compose up -d
```

Start with logs visible:
```bash
docker-compose up
```

### Stop Services

Stop services (keeps containers):
```bash
docker-compose stop
```

Stop and remove containers:
```bash
docker-compose down
```

Stop and remove containers + volumes (⚠️ deletes all data):
```bash
docker-compose down -v
```

### Restart Services

Restart all services:
```bash
docker-compose restart
```

Restart specific service:
```bash
docker-compose restart web
```

## Accessing the Application

### Web Interface

1. Open browser: http://localhost:8000
2. Login with credentials from `.env`:
   - Username: `girish` (or your configured username)
   - Password: `Girish@123` (or your configured password)
3. Configure Google Drive or upload files
4. Start chatting with your data

### API Documentation

Interactive API docs (Swagger UI):
- http://localhost:8000/docs

Alternative API docs (ReDoc):
- http://localhost:8000/redoc

### Health Check

Check application health:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
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

## Data Persistence

All data is stored in Docker volumes:

- **app-data**: Application data and SQLite database
- **uploads**: Uploaded Excel files
- **logs**: Application logs
- **tokens**: Encrypted OAuth tokens
- **chroma-data**: Vector database embeddings

### List Volumes

```bash
docker volume ls | grep gdrive-excel-rag
```

### Inspect Volume

```bash
docker volume inspect gdrive-excel-rag_chroma-data
```

### Volume Location

Volumes are stored in Docker's data directory:
- Linux: `/var/lib/docker/volumes/`
- macOS: `~/Library/Containers/com.docker.docker/Data/vms/0/`
- Windows: `C:\ProgramData\Docker\volumes\`

## Monitoring and Logs

### View Logs

All services:
```bash
docker-compose logs -f
```

Specific service:
```bash
docker-compose logs -f web
docker-compose logs -f chromadb
```

Last 100 lines:
```bash
docker-compose logs --tail=100 web
```

### Application Logs

Access logs inside container:
```bash
docker-compose exec web tail -f /app/logs/api.log
docker-compose exec web tail -f /app/logs/errors.log
docker-compose exec web tail -f /app/logs/indexing.log
docker-compose exec web tail -f /app/logs/queries.log
```

### Resource Usage

Monitor resource usage:
```bash
docker stats
```

### Health Checks

Check service health:
```bash
docker-compose ps
```

Manual health check:
```bash
curl http://localhost:8000/health
curl http://localhost:8001/api/v1/heartbeat
```

## Backup and Restore

### Backup All Data

Use the provided backup script:
```bash
./scripts/docker-backup.sh
```

Or manually:
```bash
# Create backup directory
mkdir -p backups

# Backup all volumes
docker run --rm \
  -v gdrive-excel-rag_app-data:/data/app-data \
  -v gdrive-excel-rag_uploads:/data/uploads \
  -v gdrive-excel-rag_logs:/data/logs \
  -v gdrive-excel-rag_tokens:/data/tokens \
  -v gdrive-excel-rag_chroma-data:/data/chroma-data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/backup-$(date +%Y%m%d-%H%M%S).tar.gz /data
```

### Restore from Backup

Use the provided restore script:
```bash
./scripts/docker-restore.sh backups/backup-20241129-120000.tar.gz
```

Or manually:
```bash
# Stop services
docker-compose down

# Restore volumes
docker run --rm \
  -v gdrive-excel-rag_app-data:/data/app-data \
  -v gdrive-excel-rag_uploads:/data/uploads \
  -v gdrive-excel-rag_logs:/data/logs \
  -v gdrive-excel-rag_tokens:/data/tokens \
  -v gdrive-excel-rag_chroma-data:/data/chroma-data \
  -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/backup-20241129-120000.tar.gz -C /

# Start services
docker-compose up -d
```

### Backup Individual Volumes

Backup specific volume:
```bash
docker run --rm \
  -v gdrive-excel-rag_chroma-data:/data \
  -v $(pwd)/backups:/backup \
  alpine tar czf /backup/chroma-backup-$(date +%Y%m%d).tar.gz /data
```

## Troubleshooting

### Services Won't Start

Check logs:
```bash
docker-compose logs
```

Check configuration:
```bash
docker-compose config
```

Rebuild images:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Port Already in Use

Change ports in `docker-compose.yml`:
```yaml
services:
  web:
    ports:
      - "8080:8000"  # Change 8080 to available port
```

Or stop conflicting service:
```bash
# Find process using port 8000
lsof -i :8000
# Kill process
kill -9 <PID>
```

### Out of Memory

Increase Docker memory limit:
- Docker Desktop: Settings → Resources → Memory
- Recommended: 4GB minimum, 8GB for large datasets

### Frontend Not Loading

Rebuild frontend:
```bash
cd frontend
npm install
npm run build
cd ..
docker-compose up -d --build
```

### ChromaDB Connection Issues

Check ChromaDB health:
```bash
curl http://localhost:8001/api/v1/heartbeat
```

Restart ChromaDB:
```bash
docker-compose restart chromadb
```

Check ChromaDB logs:
```bash
docker-compose logs chromadb
```

### Permission Issues

Fix volume permissions:
```bash
docker-compose exec web chown -R root:root /app/data /app/uploads /app/logs
```

### Database Locked

Stop all services and restart:
```bash
docker-compose down
docker-compose up -d
```

### API Key Issues

Verify API keys in `.env`:
```bash
docker-compose exec web env | grep API_KEY
```

Test API key:
```bash
# Test OpenAI key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

## Production Deployment

### Security Hardening

1. **Change default credentials**:
   ```bash
   WEB_AUTH_USERNAME=admin
   WEB_AUTH_PASSWORD=<strong-password>
   ```

2. **Use strong encryption keys**:
   ```bash
   JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
   TOKEN_ENCRYPTION_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(64))")
   ```

3. **Restrict CORS origins**:
   ```bash
   CORS_ORIGINS=https://yourdomain.com
   ```

4. **Use HTTPS with reverse proxy** (nginx, traefik, caddy)

5. **Enable firewall rules**:
   ```bash
   # Allow only necessary ports
   ufw allow 80/tcp
   ufw allow 443/tcp
   ufw deny 8000/tcp  # Don't expose directly
   ```

### Reverse Proxy Setup (nginx)

Example nginx configuration:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Resource Limits

Add resource limits to `docker-compose.yml`:
```yaml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Monitoring

Set up monitoring with:
- Prometheus + Grafana
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Docker stats API

### Automated Backups

Set up cron job for daily backups:
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/scripts/docker-backup.sh
```

### High Availability

For production HA setup:
1. Use external OpenSearch cluster instead of ChromaDB
2. Use external Redis for caching
3. Use external PostgreSQL for metadata
4. Deploy multiple application instances behind load balancer
5. Use shared storage (NFS, S3) for uploads

## Useful Commands

### Container Management

```bash
# List running containers
docker-compose ps

# Execute command in container
docker-compose exec web bash

# View container details
docker inspect gdrive-excel-rag-web

# Remove stopped containers
docker-compose rm
```

### Image Management

```bash
# List images
docker images

# Remove unused images
docker image prune

# Remove specific image
docker rmi gdrive-excel-rag-web
```

### Volume Management

```bash
# List volumes
docker volume ls

# Remove unused volumes
docker volume prune

# Remove specific volume (⚠️ deletes data)
docker volume rm gdrive-excel-rag_chroma-data
```

### Network Management

```bash
# List networks
docker network ls

# Inspect network
docker network inspect gdrive-excel-rag_app-network
```

### Cleanup

```bash
# Remove all stopped containers, unused networks, dangling images
docker system prune

# Remove everything including volumes (⚠️ deletes all data)
docker system prune -a --volumes
```

### Development

```bash
# Rebuild and restart after code changes
docker-compose up -d --build

# View real-time logs
docker-compose logs -f web

# Run tests in container
docker-compose exec web pytest

# Access Python shell
docker-compose exec web python

# Access database
docker-compose exec web sqlite3 /app/data/metadata.db
```

## Support

For issues and questions:
- Check logs: `docker-compose logs -f`
- Check health: `curl http://localhost:8000/health`
- Review configuration: `docker-compose config`
- Consult main README.md for application-specific help

## License

See LICENSE file in the repository root.
