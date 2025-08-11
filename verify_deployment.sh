#!/bin/bash

# FENIX Deployment Verification Script
# Quick check if everything is working

set -e

echo "🔍 FENIX Deployment Verification"
echo "================================"

cd /root/FENIX || { echo "❌ FENIX directory not found"; exit 1; }

# 1. Check container health
echo "📊 Container Status:"
docker compose ps | grep -E "(healthy|running)" && echo "✅ Containers running" || echo "❌ Container issues"

# 2. Check database schema
echo ""
echo "🗄️ Database Schema Check:"
docker exec fenix-postgres psql -U fenix -d fenix -c "
  SELECT column_name, data_type, is_nullable, column_default 
  FROM information_schema.columns 
  WHERE table_name = 'monitoring_configs' 
  AND column_name IN ('send_empty_reports', 'email_recipients');
" | grep -q "send_empty_reports" && echo "✅ send_empty_reports column exists" || echo "❌ Missing send_empty_reports column"

# 3. Check monitoring configs
echo ""
echo "⚙️ Monitoring Configurations:"
docker exec fenix-postgres psql -U fenix -d fenix -c "
  SELECT 
    name, 
    email_recipients, 
    send_empty_reports, 
    is_active 
  FROM monitoring_configs 
  ORDER BY name;
"

# 4. Test API endpoints
echo ""
echo "🌐 API Health Check:"
curl -s http://localhost:8001/health | jq .status 2>/dev/null | grep -q "healthy" && echo "✅ Eagle service healthy" || echo "❌ Eagle service issues"
curl -s http://localhost:8000/health | jq .status 2>/dev/null | grep -q "healthy" && echo "✅ Gateway service healthy" || echo "❌ Gateway service issues"

# 5. Check recent notifications
echo ""
echo "📧 Recent Email Notifications:"
docker exec fenix-postgres psql -U fenix -d fenix -c "
  SELECT 
    sent_at::date as date,
    success,
    subject,
    array_length(email_recipients, 1) as recipient_count
  FROM notification_logs 
  WHERE sent_at > NOW() - INTERVAL '24 hours'
  ORDER BY sent_at DESC;
" | head -10

# 6. Check celery worker status
echo ""
echo "🔄 Celery Worker Status:"
docker compose logs celery-worker --tail=5 | grep -E "(ready|Connected)" | tail -1 && echo "✅ Celery worker connected" || echo "❌ Celery worker issues"

# 7. Manual test available
echo ""
echo "🧪 Manual Test Commands:"
echo "# Test empty reports:"
echo "docker exec fenix-celery-worker celery -A src.services.scheduler call src.services.scheduler.manual_tender_scan --args='[\"default_windows_doors\"]'"
echo ""
echo "# Check results:"
echo "docker compose logs celery-worker --tail=20 | grep -E '(Email|empty report)'"

echo ""
echo "✅ Verification completed!"