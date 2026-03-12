# Docker Quick Start Guide

Get the Google Drive Excel RAG System running with Docker in 5 minutes!

## Prerequisites

- Docker Engine 20.10+ installed
- Docker Compose 2.0+ installed
- 4GB+ RAM available
- 10GB+ disk space

Verify:
```bash
docker --version
docker-compose --version
```

## Quick Start (5 Steps)

### 1. Configure Environment

Copy the Docker environment template:
```bash
cp .env.docker.example .env
```

### 2. Add Required Credentials

Edit `.env` and add your credentials:

```bash
# Required: Google Drive OAuth (get from https://console.cloud.google.com/)
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Required: OpenAI API Key (get from https://platform.openai.com/api-keys)
EMBEDDING_API_KEY=your_openai_api_key_here
LLM_API_KEY=your_openai_api_key_here

# Required: Generate secure keys
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

### 3. Build and Start

```bash
docker-compose up -d
```

This will:
- Build the application image (~5-10 minutes first time)
- Pull ChromaDB image
- Create volumes for data persistence
- Start all services

### 4. Verify

Check service status:
```bash
docker-compose ps
```

All services should show "healthy" status.

Check application health:
```bash
curl http://localhost:8000/health
```

### 5. Access Application

Open your browser:
- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

Login with:
- Username: `girish` (or your configured username)
- Password: `Girish@123` (or your configured password)

## What's Next?

### Configure Data Sources

1. **Google Drive**: Click "Connect Google Drive" and authorize
2. **Upload Files**: Click "Upload Files" and select Excel files

### Start Querying

1. Go to Chat page
2. Type your question about the data
3. Get answers with source citations!

## Common Commands

### View Logs
```bash
docker-compose logs -f
```

### Stop Services
```bash
docker-compose down
```

### Restart Services
```bash
docker-compose restart
```

### Backup Data
```bash
./scripts/docker-backup.sh
```

### Restore Data
```bash
./scripts/docker-restore.sh backups/backup-YYYYMMDD-HHMMSS.tar.gz
```

## Troubleshooting

### Services Won't Start

Check logs:
```bash
docker-compose logs
```

Rebuild:
```bash
docker-compose down
docker-compose up -d --build
```

### Port Already in Use

Change port in `docker-compose.yml`:
```yaml
services:
  web:
    ports:
      - "8080:8000"  # Change 8080 to available port
```

### Out of Memory

Increase Docker memory:
- Docker Desktop: Settings → Resources → Memory (set to 4GB+)

### Can't Access Application

Check if services are running:
```bash
docker-compose ps
```

Check health:
```bash
curl http://localhost:8000/health
```

View logs:
```bash
docker-compose logs web
```

## Need More Help?

- **Full Documentation**: See `DOCKER.md`
- **Test Results**: See `DOCKER_TEST_RESULTS.md`
- **Implementation Details**: See `TASK_22_DOCKER_IMPLEMENTATION.md`

## Configuration Options

### Use Different LLM Provider

Edit `.env`:
```bash
# Use Anthropic Claude
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-key-here
LLM_MODEL=claude-3-5-sonnet-20241022
```

### Use Local Embeddings (Free)

Edit `.env`:
```bash
# Use Sentence Transformers (no API key needed)
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Change Web Password

Edit `.env`:
```bash
WEB_AUTH_USERNAME=admin
WEB_AUTH_PASSWORD=your-secure-password
```

## Data Persistence

All data is stored in Docker volumes:
- **app-data**: Application database
- **uploads**: Uploaded files
- **logs**: Application logs
- **tokens**: OAuth tokens
- **chroma-data**: Vector embeddings

Data persists across container restarts!

## Backup Schedule

Set up automated daily backups:
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/scripts/docker-backup.sh
```

## Production Deployment

For production:
1. Change default password in `.env`
2. Use strong JWT and encryption keys
3. Set up HTTPS with reverse proxy (nginx, traefik)
4. Configure automated backups
5. Set up monitoring and alerting
6. Review security recommendations in `DOCKER.md`

## Support

- Check logs: `docker-compose logs -f`
- Check health: `curl http://localhost:8000/health`
- Review docs: `DOCKER.md`
- Check test results: `DOCKER_TEST_RESULTS.md`

---

**Ready to deploy?** Run `docker-compose up -d` and you're good to go! 🚀
