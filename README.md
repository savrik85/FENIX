# 🔥 FENIX - Fenestration Intelligence eXpert

**FENIX** is a comprehensive AI-driven system designed to automate and optimize business processes for window installation and supply companies. Built with a modern microservices architecture, FENIX leverages cutting-edge AI technology to streamline tender monitoring, inquiry processing, and workflow automation.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- Git

### 1. Setup Environment
```bash
# Clone repository
git clone <repository-url>
cd FENIX

# Setup environment variables
make dev-setup
# Edit .env file with your API keys and configuration
```

### 2. Start Services

**Option A: Docker (Recommended for production)**
```bash
# Build and start all services
make build
make up

# Check service status
make status
```

**Option B: Local Development**
```bash
# Start individual services locally
make dev-gateway    # API Gateway on port 8000
make dev-eagle      # AI Scrape Service on port 8001

# Or start all services locally
make start-local
```

### 3. Verify Installation
```bash
# Test services
make test-local

# Manual verification
curl http://localhost:8000/health  # Gateway
curl http://localhost:8001/health  # Eagle (AI Scrape)
```

## 🏗️ Architecture

FENIX follows a **microservices architecture** with each service running independently:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   🚪 Gateway    │    │   🦅 Eagle      │    │   🎯 Archer     │
│   Port: 8000    │    │   Port: 8001    │    │   Port: 8002    │
│   API Gateway   │    │   AI Scraping   │    │   Inquiry Proc  │
└─────────────────┘    └─────────────────┘    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   🔮 Oracle     │    │   ⚡ Bolt       │    │   🛡️ Shield     │
│   Port: 8003    │    │   Port: 8004    │    │   Port: 8005    │
│   AI Analytics  │    │   Workflow Auto │    │   Security      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Service Overview

| Service | Description | Port | Status |
|---------|-------------|------|--------|
| **🚪 Gateway** | Central API gateway and routing | 8000 | ✅ Ready |
| **🦅 Eagle** | AI-powered tender monitoring & scraping | 8001 | ✅ Ready |
| **🎯 Archer** | Inquiry processing and OCR | 8002 | 🏗️ In Development |
| **🔮 Oracle** | AI assistant and analytics | 8003 | 🏗️ In Development |
| **⚡ Bolt** | Workflow automation engine | 8004 | 🏗️ In Development |
| **🛡️ Shield** | Security and compliance | 8005 | 🏗️ In Development |
| **📦 Core** | Shared components and utilities | 8006 | 🏗️ In Development |

## 🦅 AI Scrape (Eagle Service)

The **Eagle** service is the core AI scraping component, currently **ready for use**.

### Features
- **Intelligent Tender Monitoring**: Automated tracking of procurement opportunities
- **Multi-source Support**: SAM.gov, Dodge Construction, and custom sources
- **AI-powered Extraction**: Uses Crawl4AI for intelligent data extraction
- **Relevance Filtering**: ML-based automatic assessment of opportunity relevance
- **Real-time Processing**: Background job processing with status tracking

### API Endpoints

**Base URL**: `http://localhost:8001`

```bash
# Health check
GET /health

# Service info
GET /

# Available scraping sources
GET /scrape/sources

# Start scraping job (coming soon)
POST /scrape/start
{
  "source": "sam.gov",
  "keywords": ["windows", "doors", "glazing"],
  "max_results": 50
}

# Check job status (coming soon)
GET /scrape/status/{job_id}

# Get scraping results (coming soon)
GET /scrape/results/{job_id}

# AI-powered URL crawling (coming soon)
POST /crawl/url?url=https://example.com
```

### Supported Sources

| Source | Description | Status |
|--------|-------------|--------|
| **SAM.gov** | US Government procurement opportunities | ✅ Available |
| **Dodge Construction** | Construction project leads | 🔄 Coming Soon |
| **Custom Sources** | User-defined scraping targets | 🔄 Coming Soon |

## 🛠️ Development Commands

### Docker Operations
```bash
make build          # Build all Docker containers
make up             # Start all services in containers
make down           # Stop and remove containers
make logs           # Show logs from all services
make clean          # Clean up containers, volumes, and images
make status         # Show Docker services status
```

### Local Development
```bash
make dev-gateway    # Start Gateway on localhost:8000
make dev-eagle      # Start Eagle on localhost:8001
make start-local    # Start all services locally (no Docker)
make stop-local     # Stop local services
make test-local     # Test running services
```

### Individual Services
```bash
make gateway-up     # Start only Gateway in Docker
make eagle-up       # Start only Eagle in Docker
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Core Configuration
ENVIRONMENT=development
DEBUG=true

# AI Services API Keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
CRAWL4AI_API_KEY=your_crawl4ai_key_here

# External Integrations
SAM_GOV_API_KEY=your_sam_gov_key
GOOGLE_CREDENTIALS_FILE=credentials.json
ASANA_ACCESS_TOKEN=your_asana_token

# Security
SECRET_KEY=your_secret_key_minimum_32_characters
JWT_SECRET_KEY=your_jwt_secret_key

# Scraping Configuration
DEFAULT_SCRAPING_INTERVAL=3600  # seconds
MAX_CONCURRENT_SCRAPING_JOBS=5
SCRAPING_TIMEOUT=300  # seconds
```

### Required API Keys

| Service | Required For | How to Get |
|---------|--------------|------------|
| **OpenAI** | AI-powered content analysis | [OpenAI API](https://platform.openai.com/api-keys) |
| **Crawl4AI** | Intelligent web scraping | [Crawl4AI](https://crawl4ai.com) |
| **SAM.gov** | Government tender data | [SAM.gov API](https://sam.gov/data-services) |
| **Google Sheets** | Data export integration | [Google Cloud Console](https://console.cloud.google.com) |
| **Asana** | Task management integration | [Asana Developer](https://developers.asana.com) |

## 🚦 Deployment Options

### Development Workflow

1. **Quick API Testing**:
   ```bash
   make dev-gateway
   curl http://localhost:8000/health
   ```

2. **AI Scrape Development**:
   ```bash
   make dev-gateway &
   make dev-eagle &
   # Test AI scraping endpoints
   curl http://localhost:8001/scrape/sources
   ```

3. **Full Environment Testing**:
   ```bash
   make build
   make up
   # All services running in isolated containers
   ```

### 🚀 Production Deployment

#### Automatic Deployment (CI/CD)

FENIX includes GitHub Actions workflow for automatic deployment:

1. **Setup SSH Key for GitHub Actions**:
   ```bash
   ./scripts/setup-auto-deploy.sh
   ```

2. **Configure GitHub Secrets**:
   - Go to Settings > Secrets and variables > Actions
   - Add the following secrets:
     - `SERVER_HOST`: Your server IP/domain
     - `SERVER_USER`: SSH username (e.g., root)
     - `SERVER_PORT`: SSH port (usually 22)
     - `SERVER_SSH_KEY`: Private SSH key from setup script

3. **Server Prerequisites**:
   - CentOS Stream 9 / Ubuntu 20.04+ / Debian 11+
   - Docker and Docker Compose installed
   - Git installed

4. **Automatic Deployment**:
   - Push to `main` branch triggers deployment
   - Services are automatically updated on server
   - Deployment status logged to `/var/log/fenix-deploy.log`

#### Manual Deployment

1. **Prepare Server**:
   ```bash
   # On server (CentOS example)
   yum install -y git docker-ce docker-ce-cli containerd.io docker-compose-plugin
   systemctl start docker
   systemctl enable docker
   ```

2. **Clone and Deploy**:
   ```bash
   cd /root
   git clone https://github.com/savrik85/FENIX.git fenix
   cd fenix
   cp .env.example .env
   # Edit .env with your API keys
   docker compose up -d
   ```

3. **Verify Deployment**:
   ```bash
   docker compose ps
   curl http://your-server:8000/health
   curl http://your-server:8001/health
   ```

### Communication Patterns

**API Gateway Pattern**:
```
Client Request → Gateway (8000) → Eagle (8001)
                               → Oracle (8003)
                               → Shield (8005)
```

- **Internal**: Services communicate via Docker network (`http://eagle:8001`)
- **External**: Access via localhost ports (`http://localhost:8001`)

### Network Configuration

**Docker Mode**:
- Services communicate through `fenix_default` network
- Automatic service discovery by container name
- Health checks and restart policies enabled

**Local Mode**:
- All services run on `localhost` with different ports
- Direct access without Docker proxy overhead
- Faster development iteration

## 🧪 Testing

### Automated Testing
```bash
# Run all tests (when available)
make test

# Test specific service
docker compose exec eagle pytest tests/ -v
```

### Manual Testing
```bash
# Test all services
make test-local

# Individual service health checks
curl http://localhost:8000/health  # Gateway
curl http://localhost:8001/health  # Eagle
curl http://localhost:8001/scrape/sources  # Eagle features
```

## 📁 Project Structure

```
FENIX/
├── fenix-gateway/          # 🚪 API Gateway
│   ├── src/main.py        # FastAPI application
│   ├── Dockerfile         # Container configuration
│   └── requirements.txt   # Python dependencies
├── fenix-eagle/           # 🦅 AI Scrape Service
│   ├── src/
│   │   ├── main.py        # FastAPI application
│   │   ├── services/      # Business logic
│   │   └── models/        # Data models
│   ├── tests/             # Unit tests
│   ├── Dockerfile         # Container configuration
│   └── requirements.txt   # Python dependencies
├── fenix-[other-services]/# Other microservices
├── docker-compose.yml     # Service orchestration
├── Makefile              # Development commands
├── .env.example          # Environment template
├── CLAUDE.md             # Development guide
└── README.md             # This file
```

## 🔮 Roadmap

### Phase 1: Infrastructure ✅
- [x] Microservices architecture setup
- [x] Docker containerization
- [x] API Gateway implementation
- [x] Basic CI/CD pipeline
- [x] GitHub Actions auto-deployment

### Phase 2: AI Scrape (Eagle) 🔄
- [x] Basic FastAPI structure
- [x] Health checks and service discovery
- [x] Scraping sources configuration
- [x] Crawl4AI integration ready
- [ ] SAM.gov real data scraping
- [ ] AI-powered relevance filtering

### Phase 3: Core Services 🔄
- [ ] Archer: Inquiry processing with OCR
- [ ] Oracle: AI assistant and analytics
- [ ] Bolt: Workflow automation
- [ ] Shield: Security and compliance

### Phase 4: Integrations 📋
- [ ] Google Sheets export
- [ ] Asana task management
- [ ] Email notifications
- [ ] Advanced reporting

### Phase 5: Production 🚀
- [ ] Kubernetes deployment
- [ ] Monitoring and logging
- [ ] Performance optimization
- [ ] Security hardening

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/amazing-feature`
3. **Make your changes**
4. **Test thoroughly**: `make test-local`
5. **Commit changes**: `git commit -m 'Add amazing feature'`
6. **Push to branch**: `git push origin feature/amazing-feature`
7. **Open a Pull Request**

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 📞 Support

- **Documentation**: See [CLAUDE.md](CLAUDE.md) for development guidance
- **Issues**: [GitHub Issues](https://github.com/your-repo/fenix/issues)
- **Email**: support@fenix-ai.com

---

**FENIX - Transforming windows into opportunities with AI** 🔥