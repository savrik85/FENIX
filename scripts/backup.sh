#\!/bin/bash

# FENIX Database Backup Script
# Author: Claude AI
# Version: 1.0

set -e

# Configuration
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="fenix_backup_${DATE}.sql"
RETENTION_DAYS=30

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory if it doesn't exist
if [ \! -d "$BACKUP_DIR" ]; then
    print_status "Creating backup directory..."
    mkdir -p "$BACKUP_DIR"
fi

# Check if postgres container is running
if \! docker compose ps postgres | grep -q "Up"; then
    print_error "PostgreSQL container is not running\!"
    exit 1
fi

print_status "Starting database backup..."

# Create database backup
docker compose exec -T postgres pg_dump -U fenix -d fenix --verbose > "${BACKUP_DIR}/${BACKUP_FILE}"

if [ $? -eq 0 ]; then
    print_status "✅ Database backup created: ${BACKUP_DIR}/${BACKUP_FILE}"

    # Compress the backup
    gzip "${BACKUP_DIR}/${BACKUP_FILE}"
    print_status "✅ Backup compressed: ${BACKUP_DIR}/${BACKUP_FILE}.gz"

    # Get backup size
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}.gz" | cut -f1)
    print_status "📊 Backup size: ${BACKUP_SIZE}"

else
    print_error "❌ Database backup failed\!"
    exit 1
fi

# Clean up old backups
print_status "Cleaning up old backups (older than ${RETENTION_DAYS} days)..."
find "$BACKUP_DIR" -name "fenix_backup_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# List current backups
print_status "📋 Current backups:"
ls -lah "$BACKUP_DIR"/fenix_backup_*.sql.gz 2>/dev/null || print_warning "No backup files found"

print_status "🎉 Backup process completed successfully\!"

# Optional: Copy to external location
# Uncomment and configure for production use
# print_status "Copying backup to external storage..."
# rsync -av "${BACKUP_DIR}/${BACKUP_FILE}.gz" user@backup-server:/path/to/backups/
EOF < /dev/null
