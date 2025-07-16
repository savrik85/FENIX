#\!/bin/bash

# FENIX Production Deployment Script
# Author: Claude AI
# Version: 1.0

set -e

echo "🚀 Starting FENIX Production Deployment..."
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
if [ \! -f .env ]; then
    print_error ".env file not found\!"
    print_status "Copying .env.production template..."
    cp .env.production .env
    print_warning "Please edit .env file with your production values before continuing"
    exit 1
fi

# Check if logs directory exists
if [ \! -d "logs" ]; then
    print_status "Creating logs directory..."
    mkdir -p logs
fi

# Stop existing containers if running
print_status "Stopping existing containers..."
docker compose down --remove-orphans

# Build all services
print_status "Building FENIX services..."
docker compose build --parallel

# Start database and cache first
print_status "Starting database and cache services..."
docker compose up -d postgres redis

# Wait for database to be ready
print_status "Waiting for database to be ready..."
timeout=60
while \! docker compose exec postgres pg_isready -U fenix > /dev/null 2>&1; do
    if [ $timeout -eq 0 ]; then
        print_error "Database failed to start within 60 seconds"
        exit 1
    fi
    sleep 1
    timeout=$((timeout - 1))
done

# Run database migrations
print_status "Running database migrations..."
docker compose up --no-deps migration

# Start core services
print_status "Starting FENIX core services..."
docker compose up -d eagle gateway

# Wait for services to be ready
print_status "Waiting for services to be ready..."
sleep 10

# Start background workers
print_status "Starting background workers..."
docker compose up -d celery-worker celery-beat

# Check service health
print_status "Checking service health..."
sleep 5

# Health check for Eagle
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    print_status "✅ Eagle service is healthy"
else
    print_error "❌ Eagle service health check failed"
    exit 1
fi

# Health check for Gateway
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    print_status "✅ Gateway service is healthy"
else
    print_error "❌ Gateway service health check failed"
    exit 1
fi

# Check container status
print_status "Container status:"
docker compose ps

# Show logs from last 10 lines
print_status "Recent logs:"
docker compose logs --tail=10

echo ""
echo "🎉 FENIX Deployment Complete\!"
echo "============================="
echo "📊 Services:"
echo "   - API Gateway: http://localhost:8000"
echo "   - Eagle (Monitoring): http://localhost:8001"
echo "   - Database: localhost:5432"
echo "   - Redis: localhost:6379"
echo ""
echo "🔍 Next steps:"
echo "   1. Test email: curl -X POST 'http://localhost:8001/monitoring/test-email?email=your@email.com'"
echo "   2. Check configs: curl http://localhost:8001/monitoring/configs"
echo "   3. Manual scan: curl -X POST http://localhost:8001/monitoring/trigger-scan"
echo "   4. View logs: docker compose logs -f"
echo ""
echo "🎯 Daily monitoring will run at 8:00 AM Prague time"
echo "✅ System ready for production\!"
EOF < /dev/null
