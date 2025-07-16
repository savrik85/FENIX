#\!/bin/bash

# FENIX Quick Start Script
# Author: Claude AI
# Version: 1.0

echo "🎯 FENIX Quick Start"
echo "==================="

# Check if .env exists
if [ \! -f .env ]; then
    echo "📝 Setting up environment configuration..."
    cp .env.production .env
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys and credentials\!"
    echo ""
    echo "📋 Required API keys:"
    echo "   - OPENAI_API_KEY (for AI relevance scoring)"
    echo "   - EMAIL_USERNAME and EMAIL_PASSWORD (Gmail app password)"
    echo ""
    echo "📋 Optional API keys for more data sources:"
    echo "   - SAM_GOV_API_KEY (US Government tenders - FREE)"
    echo "   - SHOVELS_AI_API_KEY (Building permits - FREE trial)"
    echo "   - CRAWL4AI_API_KEY (Enhanced web scraping)"
    echo ""
    echo "🔧 After editing .env, run this script again to start FENIX"
    exit 0
fi

# Quick deployment
echo "🚀 Starting FENIX with current configuration..."
echo ""

# Create logs directory
mkdir -p logs

# Start with testing profile (includes MailHog for email testing)
echo "📧 Starting with email testing enabled (MailHog on port 8025)"
COMPOSE_PROFILES=testing docker compose up -d --build

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Show service status
echo "📊 Service Status:"
docker compose ps

echo ""
echo "🎉 FENIX Started Successfully\!"
echo "============================="
echo ""
echo "🌐 Available Services:"
echo "   - FENIX Eagle (Monitoring): http://localhost:8001"
echo "   - API Gateway: http://localhost:8000"
echo "   - Email Testing (MailHog): http://localhost:8025"
echo ""
echo "🧪 Quick Tests:"
echo "   # Test health"
echo "   curl http://localhost:8001/health"
echo ""
echo "   # Test email (check http://localhost:8025 for result)"
echo "   curl -X POST 'http://localhost:8001/monitoring/test-email?email=test@example.com'"
echo ""
echo "   # View monitoring configurations"
echo "   curl http://localhost:8001/monitoring/configs"
echo ""
echo "   # Trigger manual scan"
echo "   curl -X POST http://localhost:8001/monitoring/trigger-scan"
echo ""
echo "📝 Next Steps:"
echo "   1. Test email functionality using MailHog"
echo "   2. Add your API keys to .env file"
echo "   3. Configure Gmail for production email"
echo "   4. Run ./scripts/deploy.sh for full production deployment"
echo ""
echo "📋 Useful Commands:"
echo "   docker compose logs -f          # View logs"
echo "   docker compose ps               # Service status"
echo "   docker compose down             # Stop all services"
echo "   ./scripts/backup.sh             # Backup database"
EOF < /dev/null
