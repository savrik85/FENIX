# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

FENIX (Fenestration Intelligence eXpert) is an AI-driven system for automating business processes in window installation and supply companies. The project uses a microservices architecture with Docker containerization.

## Architecture

The system consists of 7 microservices:
- **fenix-gateway**: API gateway and entry point for external requests
- **fenix-core**: Core business logic and orchestration
- **fenix-oracle**: AI/ML predictions and analytics
- **fenix-shield**: Security, authentication, and authorization
- **fenix-archer**: (Purpose to be determined based on implementation)
- **fenix-bolt**: (Purpose to be determined based on implementation)
- **fenix-eagle**: (Purpose to be determined based on implementation)

Each service follows the same directory structure:
```
service-name/
├── Dockerfile
├── requirements.txt
├── src/
│   └── main.py
└── tests/
```

## Development Commands

### Quick Start with Docker Compose
```bash
# Setup environment
make dev-setup
# Edit .env file with your API keys

# Build and start all services
make build
make up

# Check status
make status
make health
```

### Individual Service Development
```bash
# Run fenix-eagle (AI Scrape) in development mode
make dev-eagle

# Run API gateway in development mode  
make dev-gateway
```

### Common Docker Operations
```bash
# Build all services
docker-compose build

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Testing
```bash
# Run all tests
make test

# Test specific service
docker-compose exec eagle pytest tests/ -v
```

### Database Operations
```bash
# Setup database
make db-setup

# Run migrations
make db-migrate

# Reset database (WARNING: destructive)
make db-reset
```

## AI Scrape Implementation Status

### ✅ Completed Features
- **fenix-eagle module** with FastAPI structure
- **Docker Compose** configuration for all services
- **Crawl4AI integration** ready with Playwright browser automation
- **SAM.gov and Dodge Construction** scraper foundations
- **Mock data endpoints** for immediate testing
- **Background job processing** with Celery
- **Rate limiting and error handling**

### 🚀 Key AI Scrape Endpoints
```bash
# Start scraping job
POST http://localhost:8001/scrape/start
{
  "source": "sam.gov",
  "keywords": ["windows", "doors", "glazing"],
  "max_results": 50
}

# Check job status
GET http://localhost:8001/scrape/status/{job_id}

# Get results
GET http://localhost:8001/scrape/results/{job_id}

# AI-powered URL crawling
POST http://localhost:8001/crawl/url?url=https://example.com
```

### 🔧 Next Implementation Steps
1. **Replace mock data** with actual Crawl4AI scraping logic
2. **Add real SAM.gov API integration**
3. **Implement AI relevance filtering** via fenix-oracle
4. **Add Google Sheets and Asana integrations**
5. **Create database migrations** for persistent storage

### 🏗️ Architecture Notes
- **Microservices pattern** with Docker containerization
- **PostgreSQL** for persistent data storage
- **Redis** for caching and task queues
- **Celery** for background job processing
- **FastAPI** with async/await for high performance
- **Crawl4AI + Playwright** for intelligent web scraping

### 🔐 Required Environment Variables
```bash
# Essential for AI Scrape functionality
OPENAI_API_KEY=your_openai_key
CRAWL4AI_API_KEY=your_crawl4ai_key
SAM_GOV_API_KEY=your_sam_gov_key

# Optional integrations  
GOOGLE_CREDENTIALS_FILE=credentials.json
ASANA_ACCESS_TOKEN=your_asana_token
```