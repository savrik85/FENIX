#!/bin/bash

# FENIX Database Restore Script
# Usage: ./scripts/restore-backup.sh [backup-file]

set -e

echo "=== FENIX Database Restore ==="

# Check if running from project root
if [ ! -f "docker-compose.yml" ]; then
    echo "ERROR: Must run from FENIX project root directory"
    exit 1
fi

# Find backup file
if [ -n "$1" ]; then
    BACKUP_FILE="$1"
elif [ -d "/root/fenix-backups" ]; then
    BACKUP_FILE=$(ls /root/fenix-backups/*.sql 2>/dev/null | tail -1)
else
    echo "ERROR: No backup file specified and no backups found in /root/fenix-backups"
    echo "Usage: $0 [backup-file]"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Using backup file: $BACKUP_FILE"
echo "Backup created: $(stat -c %y "$BACKUP_FILE" 2>/dev/null || stat -f %Sm "$BACKUP_FILE")"

# Confirm restore
read -p "This will REPLACE all current database content. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Starting database restore..."

# Ensure database is running
echo "Checking database status..."
docker compose up -d postgres
sleep 5

# Wait for database to be ready
echo "Waiting for database to be ready..."
timeout=30
while [ $timeout -gt 0 ]; do
    if docker compose exec postgres pg_isready -U fenix > /dev/null 2>&1; then
        echo "Database is ready!"
        break
    fi
    sleep 2
    timeout=$((timeout-2))
done

if [ $timeout -le 0 ]; then
    echo "ERROR: Database not ready after 30 seconds"
    exit 1
fi

# Create backup of current state
echo "Creating backup of current state..."
CURRENT_BACKUP="/root/fenix-backups/pre-restore-backup-$(date +%Y%m%d-%H%M%S).sql"
docker compose exec -T postgres pg_dump -U fenix fenix > "$CURRENT_BACKUP" 2>/dev/null || true

# Drop and recreate database
echo "Dropping and recreating database..."
docker compose exec -T postgres psql -U fenix -c "DROP DATABASE IF EXISTS fenix;" postgres
docker compose exec -T postgres psql -U fenix -c "CREATE DATABASE fenix;" postgres

# Restore from backup
echo "Restoring database from backup..."
if docker compose exec -T postgres psql -U fenix fenix < "$BACKUP_FILE"; then
    echo "✅ Database restore completed successfully!"

    # Restart application services to pick up restored data
    echo "Restarting application services..."
    docker compose restart eagle gateway core oracle shield archer bolt

    # Wait and check
    sleep 10
    if curl -s http://localhost:8001/health > /dev/null; then
        TENDER_COUNT=$(curl -s http://localhost:8001/monitoring/stats | grep -o '"total_tenders":[0-9]*' | cut -d':' -f2 || echo "0")
        echo "✅ Restore verification: Database now contains $TENDER_COUNT tenders"
    else
        echo "⚠️  Application services not responding - check logs"
    fi

else
    echo "❌ Database restore failed!"
    echo "Attempting to restore previous state..."
    docker compose exec -T postgres psql -U fenix fenix < "$CURRENT_BACKUP" 2>/dev/null || true
    exit 1
fi

echo "=== Restore Complete ==="
