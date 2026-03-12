#!/bin/bash
# Docker Backup Script for Google Drive Excel RAG System
# This script backs up all Docker volumes to a compressed archive

set -e

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="backup-${TIMESTAMP}.tar.gz"
PROJECT_NAME="gdrive-excel-rag"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Docker Backup Script ===${NC}"
echo "Project: ${PROJECT_NAME}"
echo "Timestamp: ${TIMESTAMP}"
echo ""

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Check if volumes exist
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
        echo "✓ Found volume: ${volume}"
    else
        echo -e "${RED}✗ Volume not found: ${volume}${NC}"
        echo "  Run 'docker-compose up -d' to create volumes"
        exit 1
    fi
done

echo ""
echo -e "${YELLOW}Creating backup...${NC}"
echo "Backup file: ${BACKUP_DIR}/${BACKUP_FILE}"

# Create backup using Alpine container
docker run --rm \
    -v "${PROJECT_NAME}_app-data:/data/app-data:ro" \
    -v "${PROJECT_NAME}_uploads:/data/uploads:ro" \
    -v "${PROJECT_NAME}_logs:/data/logs:ro" \
    -v "${PROJECT_NAME}_tokens:/data/tokens:ro" \
    -v "${PROJECT_NAME}_chroma-data:/data/chroma-data:ro" \
    -v "$(pwd)/${BACKUP_DIR}:/backup" \
    alpine tar czf "/backup/${BACKUP_FILE}" /data

# Check if backup was created successfully
if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    echo ""
    echo -e "${GREEN}✓ Backup completed successfully!${NC}"
    echo "  File: ${BACKUP_DIR}/${BACKUP_FILE}"
    echo "  Size: ${BACKUP_SIZE}"
    echo ""
    
    # List recent backups
    echo -e "${YELLOW}Recent backups:${NC}"
    ls -lh "${BACKUP_DIR}" | tail -n 5
    echo ""
    
    # Calculate total backup size
    TOTAL_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
    echo "Total backup size: ${TOTAL_SIZE}"
    
    # Cleanup old backups (keep last 7 days)
    echo ""
    echo -e "${YELLOW}Cleaning up old backups (keeping last 7 days)...${NC}"
    find "${BACKUP_DIR}" -name "backup-*.tar.gz" -type f -mtime +7 -delete
    DELETED_COUNT=$(find "${BACKUP_DIR}" -name "backup-*.tar.gz" -type f -mtime +7 | wc -l)
    echo "Deleted ${DELETED_COUNT} old backup(s)"
    
else
    echo -e "${RED}✗ Backup failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=== Backup Complete ===${NC}"
echo ""
echo "To restore this backup, run:"
echo "  ./scripts/docker-restore.sh ${BACKUP_DIR}/${BACKUP_FILE}"
