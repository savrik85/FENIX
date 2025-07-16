# 🚀 FENIX Production Deployment Guide

FENIX (Fenestration Intelligence eXpert) is an AI-driven tender monitoring system ready for production deployment.

## ⚡ Quick Start (2 minutes)

```bash
# 1. Clone and setup
git clone <repository>
cd FENIX

# 2. Quick start with email testing
./scripts/quick-start.sh

# 3. Test the system
curl http://localhost:8001/health
curl -X POST 'http://localhost:8001/monitoring/test-email?email=test@example.com'

# 4. View test email at http://localhost:8025
```

## 🎯 Production Deployment

### **Step 1: Configure Environment**

```bash
# Copy production template
cp .env.production .env

# Edit with your credentials
vim .env  # or your preferred editor
```

### **Step 2: Required API Keys**

```bash
# Essential (system won't work without these):
OPENAI_API_KEY=sk-...                    # For AI relevance scoring
EMAIL_USERNAME=your@gmail.com            # Gmail address
EMAIL_PASSWORD=your_app_password         # Gmail app-specific password

# Recommended (more data sources):
SAM_GOV_API_KEY=...                      # US Government tenders (FREE)
SHOVELS_AI_API_KEY=...                   # Building permits (FREE trial)
CRAWL4AI_API_KEY=...                     # Enhanced web scraping
```

### **Step 3: Deploy to Production**

```bash
# Full production deployment
./scripts/deploy.sh
```

## 🔧 Gmail App Password Setup

1. Go to https://myaccount.google.com/security
2. Enable 2-step verification if not already enabled
3. Click "App passwords"
4. Generate password for "Mail"
5. Use this password in .env file

## 📊 Service Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gateway       │    │      Eagle      │    │   PostgreSQL    │
│   Port: 8000    │────│   Port: 8001    │────│   Port: 5432    │
│   (API Entry)   │    │  (Monitoring)   │    │   (Database)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
        ┌───────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
        │ Celery Beat  │  │Celery Worker│  │    Redis    │
        │ (Scheduler)  │  │ (Processor) │  │ (Cache/MQ)  │
        └──────────────┘  └─────────────┘  └─────────────┘
```

## 🕗 Monitoring Schedule

- **Daily Scan**: 8:00 AM Prague time (configurable)
- **Sources**: SAM.gov, Construction.com, NYC OpenData, Shovels.ai
- **Keywords**: windows, doors, glazing, fenestration, curtain wall, etc.
- **Email**: Instant notifications for new relevant tenders

## 🛠️ Management Commands

### **Health Checks**
```bash
# Check all services
docker compose ps

# Health endpoints
curl http://localhost:8001/health
curl http://localhost:8000/health
```

### **Manual Operations**
```bash
# Trigger manual scan
curl -X POST http://localhost:8001/monitoring/trigger-scan

# Test email notifications
curl -X POST "http://localhost:8001/monitoring/test-email?email=your@email.com"

# View monitoring configurations
curl http://localhost:8001/monitoring/configs

# Check system statistics
curl http://localhost:8001/monitoring/stats
```

### **Backup & Maintenance**
```bash
# Create database backup
./scripts/backup.sh

# View logs
docker compose logs -f

# Restart services
docker compose restart

# Update and redeploy
git pull
./scripts/deploy.sh
```

## 📧 Email Notifications

### **Production Email (Gmail)**
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=your@gmail.com
EMAIL_PASSWORD=your_app_password
DEFAULT_NOTIFICATION_EMAIL=your@gmail.com
```

### **Testing Email (MailHog)**
```bash
# Start with testing profile
COMPOSE_PROFILES=testing docker compose up -d

# View test emails at http://localhost:8025
```

## 🔍 API Endpoints

### **Core Endpoints**
- `GET /health` - Service health check
- `GET /monitoring/configs` - View monitoring configurations
- `POST /monitoring/trigger-scan` - Manual scan trigger
- `POST /monitoring/test-email` - Test email notifications

### **Scraping Endpoints**
- `GET /scrape/sources` - Available data sources
- `POST /scrape/start` - Start scraping job
- `GET /scrape/status/{job_id}` - Job status
- `GET /scrape/results/{job_id}` - Job results

## 🔒 Security Features

- ✅ Non-root container users
- ✅ Health checks and auto-restart
- ✅ Secret management via environment variables
- ✅ Rate limiting on API endpoints
- ✅ Input validation and sanitization
- ✅ Secure database connections

## 📈 Performance Optimization

### **Default Settings (Production)**
```env
# Database Performance
POSTGRES_SHARED_BUFFERS=256MB
POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
POSTGRES_MAINTENANCE_WORK_MEM=64MB

# Scraping Performance
MAX_CONCURRENT_SCRAPING_JOBS=3
BROWSER_HEADLESS=true
BROWSER_TIMEOUT=30000

# Worker Performance
CELERY_WORKER_CONCURRENCY=2
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
```

## 🔧 Troubleshooting

### **Common Issues**

**Email not working?**
```bash
# Check email configuration
docker compose logs eagle | grep -i email

# Test with MailHog first
COMPOSE_PROFILES=testing docker compose up -d
curl -X POST "http://localhost:8001/monitoring/test-email?email=test@example.com"
# Check http://localhost:8025
```

**Services not starting?**
```bash
# Check container status
docker compose ps

# View specific service logs
docker compose logs eagle
docker compose logs postgres
```

**Database connection issues?**
```bash
# Check database health
docker compose exec postgres pg_isready -U fenix

# Manual database connection
docker compose exec postgres psql -U fenix -d fenix
```

### **Log Locations**
- Application logs: `./logs/`
- Container logs: `docker compose logs <service>`

## 📋 Production Checklist

- [ ] API keys configured in .env
- [ ] Gmail app password set up
- [ ] Database backup strategy implemented
- [ ] Monitoring notifications tested
- [ ] All health checks passing
- [ ] Log rotation configured
- [ ] Resource limits appropriate for server

## 🎯 What's Next?

1. **Monitor Daily**: Check email notifications daily
2. **Review Results**: Evaluate relevance and adjust keywords
3. **Scale Up**: Add more data sources as needed
4. **Integrate**: Connect with your CRM/project management tools
5. **Optimize**: Fine-tune relevance scoring based on results

## 🆘 Support

- **Logs**: `docker compose logs -f`
- **Health**: `curl http://localhost:8001/health`
- **Status**: `docker compose ps`
- **Backup**: `./scripts/backup.sh`

---

**🎉 Your FENIX monitoring system is ready to find window and door installation opportunities! 🎯**
