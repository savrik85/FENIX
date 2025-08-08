# FENIX Monitoring System Fixes

## Root Cause Analysis

The FENIX monitoring system was experiencing 300-second timeouts because of a fundamental architectural issue:

### The Problem
- **Scheduler** (running in `celery-worker` container) was trying to communicate with `ScraperService` directly as a Python object
- **Eagle Service** (running in `eagle` container) hosts the actual initialized `ScraperService` with Crawl4AI
- These are **separate containers** - the scheduler's local `ScraperService` instance was never initialized
- Result: Jobs were created but never executed, leading to timeouts

### Architecture Before Fix
```
celery-worker container:
├── Scheduler creates ScraperService() locally
├── ScraperService (uninitialized, no Crawl4AI)
└── ❌ Jobs hang indefinitely

eagle container:
├── FastAPI service with ScraperService
├── ScraperService (initialized with Crawl4AI)
└── ✅ Actual scraping capability
```

## The Solution

### 1. HTTP-Based Inter-Service Communication

Created `HTTPClientService` (`/Users/savrik/Projects/python/FENIX/fenix-eagle/src/services/http_client_service.py`):
- Uses `aiohttp` for async HTTP communication
- Communicates with Eagle service via REST API endpoints
- Proper timeout handling (10 minutes for complex jobs)
- Health checks before starting operations
- Robust error handling and retry logic

### 2. Updated Scheduler Architecture

Modified `scheduler.py` to use HTTP communication:
- Replaced direct `ScraperService()` calls with `HTTPClientService`
- Added health checks before starting monitoring scans
- Increased timeouts to 600 seconds (10 minutes) for complex scraping jobs
- Better error reporting and recovery

### Architecture After Fix
```
celery-worker container:
├── Scheduler uses HTTPClientService
├── HTTP calls to eagle:8001
└── ✅ Proper inter-service communication

eagle container:
├── FastAPI service receives HTTP requests
├── ScraperService (initialized with Crawl4AI)
└── ✅ Jobs executed successfully
```

## Key Changes Made

### 1. New HTTP Client Service
**File:** `/Users/savrik/Projects/python/FENIX/fenix-eagle/src/services/http_client_service.py`
- Async HTTP client using aiohttp
- Methods: `create_scraping_job()`, `get_job_status()`, `get_job_results()`
- Built-in timeout and error handling
- Health check functionality

### 2. Updated Scheduler
**File:** `/Users/savrik/Projects/python/FENIX/fenix-eagle/src/services/scheduler.py`
- Import `HTTPClientService` instead of `ScraperService`
- Health check before starting scans
- Increased timeouts (300s → 600s)
- Better error reporting in scan results
- Proper resource cleanup

### 3. Configuration Updates
**File:** `/Users/savrik/Projects/python/FENIX/fenix-eagle/src/config.py`
- Added `eagle_service_url: str = "http://eagle:8001"`
- Configurable service discovery

### 4. Testing Infrastructure
**Files:**
- `/Users/savrik/Projects/python/FENIX/test_monitoring_flow.py`
- `/Users/savrik/Projects/python/FENIX/scripts/verify_deployment.py`

## Testing the Fixes

### 1. Deployment Verification
```bash
cd /Users/savrik/Projects/python/FENIX
python scripts/verify_deployment.py
```

This script checks:
- Container health status
- Service connectivity
- Database/Redis connections
- Celery worker status
- API endpoint functionality

### 2. End-to-End Monitoring Test
```bash
python test_monitoring_flow.py
```

This script tests:
- Direct scraping jobs (should complete in ~3 seconds)
- Monitoring configuration creation
- Manual monitoring scan triggers
- Email notification system
- Statistics endpoints

### 3. Manual Testing Steps

1. **Start the system:**
   ```bash
   docker compose up -d
   ```

2. **Check all services are healthy:**
   ```bash
   python scripts/verify_deployment.py
   ```

3. **Test direct scraping:**
   ```bash
   curl -X POST "http://localhost:8001/scrape/start" \
        -H "Content-Type: application/json" \
        -d '{
          "source": "sam.gov",
          "keywords": ["windows", "glazing"],
          "max_results": 10
        }'
   ```

4. **Create monitoring configuration:**
   ```bash
   curl -X POST "http://localhost:8001/monitoring/config" \
        -H "Content-Type: application/json" \
        -d '{
          "name": "Test Monitoring",
          "keywords": ["windows", "doors", "glazing"],
          "sources": ["sam.gov"],
          "emails": ["test@example.com"]
        }'
   ```

5. **Trigger manual scan:**
   ```bash
   curl -X POST "http://localhost:8001/monitoring/trigger-scan"
   ```

6. **Check Celery logs:**
   ```bash
   docker compose logs -f celery-worker
   ```

## Expected Results

### Before Fixes:
- ❌ Monitoring scans timeout after 300 seconds
- ❌ "Job did not complete within 300 seconds" errors
- ❌ No actual scraping performed

### After Fixes:
- ✅ Monitoring scans complete successfully within 3-10 seconds
- ✅ Real tender data returned from scraping sources
- ✅ Email notifications sent for new tenders
- ✅ Proper error handling and recovery

## Monitoring the System

### Log Locations:
```bash
# Scheduler/Worker logs
docker compose logs -f celery-worker

# Eagle service logs
docker compose logs -f eagle

# Beat scheduler logs
docker compose logs -f celery-beat
```

### Key Log Messages:
- `"Performing health check on Eagle service..."` - Health check started
- `"Successfully created job {job_id} for {source}"` - Job creation success
- `"Job {job_id} completed successfully"` - Job completion
- `"Found {count} new tenders for config {name}"` - Successful scan results

### Email Testing:
- MailHog web interface: http://localhost:8025
- All test emails will appear here in development

## Production Deployment Notes

1. **Environment Variables:**
   - Set `EAGLE_SERVICE_URL` if using different service names
   - Configure email SMTP settings for real notifications
   - Set appropriate API keys for scraping sources

2. **Scaling:**
   - HTTP-based communication allows easy horizontal scaling
   - Multiple celery workers can communicate with same Eagle service
   - Eagle service can be load-balanced if needed

3. **Monitoring:**
   - Add health check endpoints to load balancers
   - Monitor HTTP client connection pools
   - Set up alerts for failed monitoring scans

## Troubleshooting

### Common Issues:

1. **"Eagle service is not healthy"**
   - Check if Eagle container is running: `docker compose ps eagle`
   - Check Eagle logs: `docker compose logs eagle`
   - Verify network connectivity between containers

2. **HTTP timeouts**
   - Check if Eagle service is overloaded
   - Increase timeouts in HTTPClientService if needed
   - Monitor system resources

3. **Job creation fails**
   - Verify API payload format matches FastAPI models
   - Check Eagle service health endpoint
   - Review source configuration

4. **No email notifications**
   - Check SMTP configuration in environment variables
   - Verify MailHog is running (development)
   - Check email service logs

The monitoring system should now work reliably with proper inter-service communication and robust error handling.
