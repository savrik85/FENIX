#!/bin/bash

# FENIX Rollback Script
# Use if deployment fails and you need to return to previous version

set -e

echo "⚠️ FENIX ROLLBACK - Reverting to previous version"
echo "================================================="

cd /root/FENIX || { echo "❌ FENIX directory not found"; exit 1; }

# 1. Stop current containers
echo "🛑 Stopping current containers..."
docker compose down

# 2. Checkout previous commit (before empty reports)
echo "🔄 Reverting to previous commit..."
git log --oneline -5
echo ""
read -p "Enter commit hash to rollback to (or press Enter for previous commit): " COMMIT_HASH

if [ -z "$COMMIT_HASH" ]; then
    COMMIT_HASH="HEAD~1"
fi

git checkout $COMMIT_HASH

# 3. Rebuild with old code
echo "🔨 Rebuilding with previous version..."
docker compose build --no-cache

# 4. Start services
echo "🚀 Starting services with old version..."
docker compose up -d

# 5. Wait and check
sleep 20
echo "📊 Service status after rollback:"
docker compose ps

# 6. Optional: Remove empty reports column (if needed)
echo ""
read -p "Remove send_empty_reports column from database? (y/N): " REMOVE_COLUMN

if [ "$REMOVE_COLUMN" = "y" ] || [ "$REMOVE_COLUMN" = "Y" ]; then
    echo "🗄️ Removing send_empty_reports column..."
    docker exec fenix-postgres psql -U fenix -d fenix -c "
        ALTER TABLE monitoring_configs DROP COLUMN IF EXISTS send_empty_reports;
    "
fi

echo "✅ Rollback completed!"
echo "📊 System is now running previous version without empty reports"