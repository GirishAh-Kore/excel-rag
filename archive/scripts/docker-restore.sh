#!/bin/bash
# Docker Restore Script for Google Drive Excel RAG System
# This script restores Docker volumes from a backup archive

set -e

# Configuration
PROJECT_NAME="gdrive-excel-rag"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Docker Restore Script ===${NC}"
echo "Project: ${PROJECT_NAME}"
echo ""

# Check if backup file is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo ""
    echo "Usage: $0 <backup-file>"
    echo ""
    echo "Example:"
    echo "  $0 backups/backup-20241129-120000.tar.gz"
    echo ""
    echo "Available backups:"
    ls -lh backups/backup-*.tar.gz 2>/dev/null || echo "  No backups found"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo -e "${RED}Error: Backup file not found: ${BACKUP_FILE}${NC}"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup file: ${BACKUP_FILE}"
echo "Backup size: ${BACKUP_SIZE}"
echo ""

# Warning
echo -e "${YELLOW}WARNING: This will overwrite all existing data!${NC}"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read -r

# Stop services
echo ""
echo -e "${YELLOW}Stopping services...${NC}"
docker-compose down

# Check if volumes exist, create if they don't
echo ""
echo -e "${YELLOW}Checking volumes...${NC}"
VOLUMES=(
    "${PROJECT_NAME}_app-data"
    "${PROJECT_NAME}_uploads"
    "${PROJECT_NAME}_logs"
    "${PROJECT_NAME}_tokens"
    "${PROJECT_NAME}_chroma-data"
)

for volume in "${VOLUMES[@]}"; do
    if docker volume inspect "${volume}" > /dev/null 2>&1; then
        echo "✓ Volume exists: ${volume}"
    else
        echo "✓ Creating volume: ${volume}"
        docker volume create "${volume}"
    fi
done

# Restore backup
echo ""
echo -e "${YELLOW}Restoring backup...${NC}"
docker run --rm \
    -v "${PROJECT_NAME}_app-data:/data/app-data" \
    -v "${PROJECT_NAME}_uploads:/data/uploads" \
    -v "${PROJECT_NAME}_logs:/data/logs" \
    -v "${PROJECT_NAME}_tokens:/data/tokens" \
    -v "${PROJECT_NAME}_chroma-data:/data/chroma-data" \
    -v "$(pwd)/$(dirname ${BACKUP_FILE}):/backup" \
    alpine tar xzf "/backup/$(basename ${BACKUP_FILE})" -C /

# Verify restore
echo ""
echo -e "${YELLOW}Verifying restore...${NC}"
for volume in "${VOLUMES[@]}"; do
    SIZE=$(docker run --rm -v "${volume}:/data" alpine du -sh /data | cut -f1)
    echo "✓ ${volume}: ${SIZE}"
done

# Start services
echo ""
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

# Wait for services to be healthy
echo ""
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check health
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Application is healthy${NC}"
else
    echo -e "${YELLOW}⚠ Application may still be starting up${NC}"
    echo "  Check status with: docker-compose ps"
    echo "  Check logs with: docker-compose logs -f"
fi

echo ""
echo -e "${GREEN}=== Restore Complete ===${NC}"
echo ""
echo "Services are starting up. Check status with:"
echo "  docker-compose ps"
echo "  docker-compose logs -f"
echo ""
echo "Access the application at:"
echo "  http://localhost:8000"
