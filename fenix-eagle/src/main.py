import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .models.tender_models import TenderData
from .services.crawler_service import CrawlerService
from .services.scraper_service import ScraperService


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global services
scraper_service: ScraperService | None = None
crawler_service: CrawlerService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app"""
    global scraper_service, crawler_service

    # Startup
    logger.info("Starting FENIX Eagle - Tender Monitoring Agent")
    scraper_service = ScraperService()
    crawler_service = CrawlerService()

    # Initialize services
    await scraper_service.initialize()
    await crawler_service.initialize()

    yield

    # Shutdown
    logger.info("Shutting down FENIX Eagle")
    if scraper_service:
        await scraper_service.cleanup()
    if crawler_service:
        await crawler_service.cleanup()


app = FastAPI(
    title="FENIX Eagle - Tender Monitoring Agent",
    description="AI-powered tender monitoring and scraping service",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# Request/Response Models
class ScrapingRequest(BaseModel):
    source: str = Field(
        ...,
        description="Scraping source (e.g., 'sam.gov', 'dodge', 'construction.com', 'nyc.opendata', 'shovels.ai')",
    )
    keywords: list[str] = Field(default=[], description="Keywords to search for")
    filters: dict[str, Any] = Field(default={}, description="Additional filters")
    max_results: int = Field(default=100, description="Maximum number of results")


class ScrapingResponse(BaseModel):
    job_id: str
    status: str
    message: str
    estimated_completion: datetime | None = None


class TenderResponse(BaseModel):
    tenders: list[TenderData]
    total_count: int
    job_info: dict[str, Any]


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "fenix-eagle",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "message": "FENIX Eagle - AI Scrape Service",
        "status": "ready",
        "features": [
            "Tender monitoring",
            "AI-powered scraping",
            "SAM.gov integration",
            "Construction.com integration",
            "NYC Open Data integration",
            "Shovels AI integration",
            "Mock data for testing",
        ],
        "endpoints": {
            "health": "/health",
            "sources": "/scrape/sources",
            "start_job": "POST /scrape/start",
            "job_status": "GET /scrape/status/{job_id}",
            "job_results": "GET /scrape/results/{job_id}",
            "list_jobs": "GET /scrape/jobs",
        },
    }


# Scraping endpoints
@app.post("/scrape/start", response_model=ScrapingResponse)
async def start_scraping(request: ScrapingRequest, background_tasks: BackgroundTasks):
    """Start a new scraping job"""
    try:
        if not scraper_service:
            raise HTTPException(status_code=503, detail="Scraper service not initialized")

        job = await scraper_service.create_job(
            source=request.source,
            keywords=request.keywords,
            filters=request.filters,
            max_results=request.max_results,
        )

        # Start scraping in background
        background_tasks.add_task(scraper_service.execute_scraping_job, job.job_id)

        return ScrapingResponse(
            job_id=job.job_id,
            status="started",
            message=f"Scraping job started for {request.source}",
            estimated_completion=job.estimated_completion,
        )

    except Exception as e:
        logger.error(f"Error starting scraping job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scrape/status/{job_id}")
async def get_scraping_status(job_id: str):
    """Get status of a scraping job"""
    try:
        if not scraper_service:
            raise HTTPException(status_code=503, detail="Scraper service not initialized")

        status = await scraper_service.get_job_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scrape/results/{job_id}", response_model=TenderResponse)
async def get_scraping_results(job_id: str):
    """Get results of a completed scraping job or all tenders from database"""
    try:
        if job_id == "all":
            # Special case: return all tenders from database
            from sqlalchemy import desc

            from .database.models import SessionLocal, StoredTender

            db = SessionLocal()
            try:
                tenders = db.query(StoredTender).order_by(desc(StoredTender.created_at)).limit(100).all()

                tender_list = []
                for tender in tenders:
                    tender_data = TenderData(
                        tender_id=tender.tender_id or str(tender.id),
                        title=tender.title,
                        description=tender.description or "",
                        source=tender.source,
                        source_url=tender.source_url or "",
                        posting_date=tender.posting_date or tender.created_at,
                        response_deadline=tender.response_deadline,
                        estimated_value=tender.estimated_value,
                        location=tender.location,
                        naics_codes=tender.naics_codes or [],
                        keywords_found=tender.keywords_found or [],
                        relevance_score=tender.relevance_score,
                        contact_info=tender.contact_info or {},
                        requirements=tender.requirements or [],
                        extracted_data=tender.extracted_data or {},
                        created_at=tender.created_at or tender.posting_date,
                    )
                    tender_list.append(tender_data)

                return TenderResponse(
                    tenders=tender_list,
                    total_count=len(tender_list),
                    job_info={
                        "job_id": "all",
                        "status": "completed",
                        "source": "database",
                        "created_at": "database_query",
                    },
                )
            finally:
                db.close()

        # Normal case: get specific job results
        if not scraper_service:
            raise HTTPException(status_code=503, detail="Scraper service not initialized")

        results = await scraper_service.get_job_results(job_id)
        if not results:
            raise HTTPException(status_code=404, detail="Results not found")

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/scrape/jobs")
async def list_scraping_jobs(status: str | None = None, source: str | None = None, limit: int = 50):
    """List scraping jobs with optional filters"""
    try:
        if not scraper_service:
            raise HTTPException(status_code=503, detail="Scraper service not initialized")

        jobs = await scraper_service.list_jobs(status=status, source=source, limit=limit)

        return {"jobs": jobs, "total_count": len(jobs)}

    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Crawler endpoints
@app.post("/crawl/url")
async def crawl_url(
    url: str,
    background_tasks: BackgroundTasks,
    extract_keywords: list[str] = None,
    ai_extract: bool = True,
):
    """Crawl a specific URL using AI-powered extraction"""
    if extract_keywords is None:
        extract_keywords = []

    try:
        if not crawler_service:
            raise HTTPException(status_code=503, detail="Crawler service not initialized")

        job_id = await crawler_service.crawl_url(url=url, extract_keywords=extract_keywords, ai_extract=ai_extract)

        return {
            "job_id": job_id,
            "status": "started",
            "message": f"Crawling started for {url}",
        }

    except Exception as e:
        logger.error(f"Error crawling URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Configuration endpoints
@app.get("/scrape/sources")
async def get_available_sources():
    """Get list of available scraping sources"""
    return {
        "sources": [
            {
                "id": "sam.gov",
                "name": "SAM.gov",
                "description": "US Government procurement opportunities",
                "supported_filters": ["naics_code", "location", "value_range"],
                "status": "available",
            },
            {
                "id": "dodge",
                "name": "Dodge Construction",
                "description": "Construction project leads",
                "supported_filters": ["project_type", "location", "value_range"],
                "status": "mock_data_only",
            },
            {
                "id": "construction.com",
                "name": "Construction.com",
                "description": "Dodge Construction Network - commercial construction projects",
                "supported_filters": [
                    "project_type",
                    "location",
                    "value_range",
                    "project_stage",
                ],
                "status": "available",
            },
            {
                "id": "nyc.opendata",
                "name": "NYC Open Data",
                "description": "NYC Department of Buildings permit data - FREE API",
                "supported_filters": [
                    "borough",
                    "permit_type",
                    "work_type",
                    "date_range",
                ],
                "status": "available",
            },
            {
                "id": "shovels.ai",
                "name": "Shovels AI",
                "description": "Building permits and contractor data - FREE TRIAL (1000 requests)",
                "supported_filters": [
                    "geo_id",
                    "contractor_id",
                    "permit_type",
                    "date_range",
                ],
                "status": "available",
            },
        ]
    }


@app.get("/scrape/keywords")
async def get_suggested_keywords():
    """Get suggested keywords for fenestration industry"""
    return {
        "categories": {
            "windows": [
                "windows",
                "replacement windows",
                "aluminum windows",
                "vinyl windows",
            ],
            "doors": ["doors", "entrance doors", "patio doors", "sliding doors"],
            "glazing": ["glazing", "curtain wall", "storefront", "commercial glazing"],
            "installation": [
                "installation",
                "window installation",
                "door installation",
            ],
            "materials": ["fenestration", "glass", "frames", "hardware"],
        },
        "suggested": [
            "windows",
            "doors",
            "fenestration",
            "glazing",
            "curtain wall",
            "storefront",
            "aluminum windows",
            "vinyl windows",
            "installation",
            "replacement windows",
            "commercial glazing",
            "residential windows",
        ],
    }


# Monitoring endpoints
class MonitoringConfigRequest(BaseModel):
    name: str
    keywords: list[str]
    sources: list[str]
    emails: list[str] = Field(description="List of email addresses for notifications")
    filters: dict[str, Any] = Field(default={}, description="Additional filters")


@app.post("/monitoring/config")
async def create_monitoring_config(request: MonitoringConfigRequest):
    """Create new monitoring configuration"""
    try:
        from .database.models import MonitoringConfig, get_db

        db = next(get_db())

        config = MonitoringConfig(
            name=request.name,
            keywords=request.keywords,
            sources=request.sources,
            email_recipients=request.emails,
            filters=request.filters,
            is_active=True,
        )

        db.add(config)
        db.commit()

        return {
            "message": "Monitoring configuration created successfully",
            "config_id": str(config.id),
            "config_name": config.name,
            "email_recipients": request.emails,
        }

    except Exception as e:
        logger.error(f"Error creating monitoring config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/monitoring/configs")
async def get_monitoring_configs():
    """Get all monitoring configurations"""
    try:
        from .database.models import MonitoringConfig, get_db

        db = next(get_db())
        configs = db.query(MonitoringConfig).all()

        return {
            "configs": [
                {
                    "id": str(config.id),
                    "name": config.name,
                    "keywords": config.keywords,
                    "sources": config.sources,
                    "email_recipients": config.email_recipients,
                    "is_active": config.is_active,
                    "created_at": config.created_at,
                    "updated_at": config.updated_at,
                }
                for config in configs
            ]
        }

    except Exception as e:
        logger.error(f"Error getting monitoring configs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/monitoring/test-email")
async def test_email_notification(email: str):
    """Test email notification system"""
    try:
        from .services.email_service import EmailService

        email_service = EmailService()
        result = await email_service.send_test_email(email)

        return {
            "message": "Test email sent" if result["success"] else "Failed to send test email",
            "success": result["success"],
            "details": result,
        }

    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/monitoring/trigger-scan")
async def trigger_manual_scan(config_name: str = None):
    """Manually trigger monitoring scan"""
    try:
        from .services.scheduler import manual_tender_scan

        # Trigger Celery task
        task = manual_tender_scan.delay(config_name)

        return {
            "message": "Manual scan triggered",
            "task_id": task.id,
            "config_name": config_name or "all",
        }

    except Exception as e:
        logger.error(f"Error triggering manual scan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/monitoring/stats")
async def get_monitoring_statistics():
    """Get monitoring system statistics"""
    try:
        from .services.deduplication_service import DeduplicationService

        dedup_service = DeduplicationService()
        stats = await dedup_service.get_duplicate_statistics()

        return {
            "monitoring_stats": stats,
            "system_info": {
                "daily_scan_time": (
                    f"{getattr(settings, 'daily_scan_hour', 8)}:{getattr(settings, 'daily_scan_minute', 0):02d}"
                ),
                "monitoring_enabled": getattr(settings, "monitoring_enabled", True),
                "default_notification_email": getattr(settings, "default_notification_email", "not_configured"),
            },
        }

    except Exception as e:
        logger.error(f"Error getting monitoring stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
