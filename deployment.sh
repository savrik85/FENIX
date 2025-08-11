#!/bin/bash

# FENIX Empty Reports Deployment Script
# Run this on production server 69.55.55.8

set -e  # Exit on error

echo "🚀 Starting FENIX deployment with empty reports..."

# 1. Navigate to FENIX directory
cd /root/FENIX || { echo "❌ FENIX directory not found"; exit 1; }

echo "📁 Current directory: $(pwd)"

# 2. Pull latest code
echo "📥 Pulling latest code..."
git pull origin main

# 3. Check current containers
echo "📊 Current container status:"
docker compose ps

# 4. Stop containers
echo "🛑 Stopping containers..."
docker compose down

# 5. Add database column (with error handling)
echo "🗄️ Adding send_empty_reports column to database..."
docker compose up -d postgres redis
sleep 10

# Wait for postgres to be ready
echo "⏳ Waiting for database to be ready..."
until docker exec fenix-postgres pg_isready -U fenix -d fenix; do
  echo "Waiting for database..."
  sleep 2
done

# Add column if it doesn't exist
docker exec fenix-postgres psql -U fenix -d fenix -c "
  DO \$\$ 
  BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name='monitoring_configs' AND column_name='send_empty_reports') THEN
      ALTER TABLE monitoring_configs ADD COLUMN send_empty_reports BOOLEAN DEFAULT false;
      RAISE NOTICE 'Column send_empty_reports added successfully';
    ELSE
      RAISE NOTICE 'Column send_empty_reports already exists';
    END IF;
  END
  \$\$;
"

# 6. Configure monitoring configs for empty reports
echo "⚙️ Configuring monitoring configs..."
docker exec fenix-postgres psql -U fenix -d fenix -c "
  UPDATE monitoring_configs 
  SET 
    send_empty_reports = true,
    email_recipients = '[\"petr.pechousek@gmail.com\", \"savrikk@gmail.com\"]'
  WHERE name = 'default_windows_doors';
  
  SELECT name, email_recipients, send_empty_reports 
  FROM monitoring_configs;
"

# 7. Stop database containers
echo "🛑 Stopping database containers for rebuild..."
docker compose down

# 8. Rebuild all containers
echo "🔨 Rebuilding containers with new code..."
docker compose build --no-cache

# 9. Start all services
echo "🚀 Starting all services..."
docker compose up -d

# 10. Wait for services to be healthy
echo "⏳ Waiting for services to be healthy..."
sleep 30

# 11. Check service status
echo "📊 Final container status:"
docker compose ps

# 12. Test empty report functionality
echo "🧪 Testing empty reports functionality..."
sleep 10

# Get monitoring config names
CONFIGS=$(docker exec fenix-postgres psql -U fenix -d fenix -t -c "SELECT name FROM monitoring_configs WHERE is_active = true;" | xargs)

echo "📋 Active configs: $CONFIGS"

# Test manual scan (should trigger empty reports for configs with send_empty_reports=true)
echo "🔄 Running manual scan to test empty reports..."
JOB_ID=$(docker exec fenix-celery-worker celery -A src.services.scheduler call src.services.scheduler.manual_tender_scan --args='["default_windows_doors"]')
echo "📝 Scan job ID: $JOB_ID"

# Wait and check logs
sleep 20
echo "📋 Recent worker logs:"
docker compose logs celery-worker --tail=30 | grep -E "(Email|empty report|success|error)" || echo "No relevant log entries found"

# 13. Check notification logs in database
echo "📊 Recent notifications in database:"
docker exec fenix-postgres psql -U fenix -d fenix -c "
  SELECT 
    success,
    email_recipients,
    subject,
    sent_at
  FROM notification_logs 
  ORDER BY sent_at DESC 
  LIMIT 5;
"

echo "✅ Deployment completed!"
echo ""
echo "📧 Email types now available:"
echo "  🎯 New tenders found → Detailed tender notification"  
echo "  📊 No new tenders + empty_reports=true → Empty report notification"
echo "  ❌ No new tenders + empty_reports=false → No email sent"
echo ""
echo "🔧 To manage empty reports:"
echo "  Enable:  UPDATE monitoring_configs SET send_empty_reports = true WHERE name = 'config_name';"
echo "  Disable: UPDATE monitoring_configs SET send_empty_reports = false WHERE name = 'config_name';"
echo ""
echo "🎉 FENIX monitoring system is now fully operational with empty reports!"