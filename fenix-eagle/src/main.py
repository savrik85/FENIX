import json
import logging
import os
import secrets
import urllib.parse
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
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
        description="Scraping source (sam.gov, dodge, construction.com, nyc.opendata, shovels.ai, autodesk_acc)",
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
            "Autodesk Construction Cloud integration",
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


@app.get("/scrape/results/{job_id}")
async def get_scraping_results(job_id: str):
    """Get results of a completed scraping job or all tenders from database"""
    try:
        if job_id == "all":
            # Special case: return all tenders from database (bypass Pydantic)
            from sqlalchemy import desc

            from .database.models import SessionLocal, StoredTender

            db = SessionLocal()
            try:
                tenders = db.query(StoredTender).order_by(desc(StoredTender.created_at)).limit(100).all()

                tender_list = []
                for tender in tenders:
                    tender_data = {
                        "tender_id": tender.tender_id or str(tender.id),
                        "title": tender.title,
                        "description": tender.description or "",
                        "source": tender.source,
                        "source_url": tender.source_url or "",
                        "posting_date": tender.posting_date.isoformat() if tender.posting_date else None,
                        "response_deadline": tender.response_deadline.isoformat() if tender.response_deadline else None,
                        "estimated_value": tender.estimated_value,
                        "location": tender.location,
                        "naics_codes": tender.naics_codes or [],
                        "keywords_found": tender.keywords_found or [],
                        "relevance_score": tender.relevance_score,
                        "contact_info": tender.contact_info or {},
                        "requirements": tender.requirements or [],
                        "extracted_data": tender.extracted_data or {},
                        "created_at": tender.created_at.isoformat() if tender.created_at else None,
                    }
                    tender_list.append(tender_data)

                return {
                    "tenders": tender_list,
                    "total_count": len(tender_list),
                    "job_info": {
                        "job_id": "all",
                        "status": "completed",
                        "source": "database",
                        "created_at": "database_query",
                    },
                }
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
            {
                "id": "autodesk_acc",
                "name": "Autodesk Construction Cloud",
                "description": "Construction project data, issues, RFIs, and documents",
                "supported_filters": [
                    "project_id",
                    "keywords",
                    "data_types",
                    "location",
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


@app.post("/database/fix-schema")
async def fix_database_schema():
    """Fix database schema issues"""
    try:
        from sqlalchemy import text

        from .database.models import engine

        with engine.connect() as conn:
            # Add missing send_empty_reports column
            try:
                conn.execute(
                    text(
                        "ALTER TABLE monitoring_configs ADD COLUMN IF NOT EXISTS "
                        "send_empty_reports BOOLEAN DEFAULT FALSE"
                    )
                )
                conn.commit()
                logger.info("Added send_empty_reports column successfully")
            except Exception as e:
                logger.warning(f"Column may already exist: {e}")

            return {"success": True, "message": "Database schema fixed"}

    except Exception as e:
        logger.error(f"Error fixing database schema: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Monitoring and Scan Log endpoints
@app.get("/monitoring/scan-logs")
async def get_scan_logs(limit: int = 20, status: str = None, config_name: str = None):
    """Get scan log history for monitoring"""
    try:
        from .database.models import ScanLog, SessionLocal

        db = SessionLocal()
        try:
            query = db.query(ScanLog).order_by(ScanLog.started_at.desc())

            # Apply filters
            if status:
                query = query.filter(ScanLog.status == status)
            if config_name:
                query = query.filter(ScanLog.config_name == config_name)

            logs = query.limit(limit).all()

            scan_logs = []
            for log in logs:
                scan_logs.append(
                    {
                        "id": str(log.id),
                        "config_name": log.config_name,
                        "scan_type": log.scan_type,
                        "started_at": log.started_at.isoformat() if log.started_at else None,
                        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                        "duration_seconds": log.duration_seconds,
                        "status": log.status,
                        "tenders_found": log.tenders_found or 0,
                        "new_tenders": log.new_tenders or 0,
                        "relevant_tenders": log.relevant_tenders or 0,
                        "sources_scanned": log.sources_scanned or [],
                        "sources_configured": log.sources_configured or [],
                        "keywords_used": log.keywords_used or [],
                        "error_message": log.error_message,
                        "warnings": log.warnings or [],
                        "triggered_by": log.triggered_by,
                    }
                )

            return {"scan_logs": scan_logs, "total_count": len(scan_logs)}

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error getting scan logs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/monitoring/scan-logs/{scan_id}")
async def get_scan_log_detail(scan_id: str):
    """Get detailed information about a specific scan"""
    try:
        from uuid import UUID

        from .database.models import ScanLog, SessionLocal

        db = SessionLocal()
        try:
            log = db.query(ScanLog).filter(ScanLog.id == UUID(scan_id)).first()
            if not log:
                raise HTTPException(status_code=404, detail="Scan log not found")

            return {
                "id": str(log.id),
                "config_name": log.config_name,
                "scan_type": log.scan_type,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "duration_seconds": log.duration_seconds,
                "status": log.status,
                "tenders_found": log.tenders_found or 0,
                "new_tenders": log.new_tenders or 0,
                "duplicate_tenders": log.duplicate_tenders or 0,
                "relevant_tenders": log.relevant_tenders or 0,
                "notifications_sent": log.notifications_sent or 0,
                "sources_scanned": log.sources_scanned or [],
                "sources_configured": log.sources_configured or [],
                "keywords_used": log.keywords_used or [],
                "filters_applied": log.filters_applied or {},
                "error_message": log.error_message,
                "warnings": log.warnings or [],
                "failed_sources": log.failed_sources or [],
                "triggered_by": log.triggered_by,
                "scan_metadata": log.scan_metadata or {},
            }

        finally:
            db.close()

    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid scan ID format") from e
    except Exception as e:
        logger.error(f"Error getting scan log detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/monitoring/scan-stats")
async def get_scan_statistics():
    """Get scanning statistics for dashboard"""
    try:
        from datetime import datetime, timedelta

        from sqlalchemy import func

        from .database.models import ScanLog, SessionLocal

        db = SessionLocal()
        try:
            # Recent scan stats (last 7 days)
            week_ago = datetime.now() - timedelta(days=7)

            # Latest scan
            latest_scan = db.query(ScanLog).order_by(ScanLog.started_at.desc()).first()

            # Counts by status (last 7 days)
            status_counts = (
                db.query(ScanLog.status, func.count(ScanLog.id))
                .filter(ScanLog.started_at >= week_ago)
                .group_by(ScanLog.status)
                .all()
            )

            # Daily stats (last 7 days)
            daily_stats = (
                db.query(
                    func.date(ScanLog.started_at).label("date"),
                    func.count(ScanLog.id).label("scan_count"),
                    func.sum(ScanLog.new_tenders).label("total_new_tenders"),
                    func.avg(ScanLog.duration_seconds).label("avg_duration"),
                )
                .filter(ScanLog.started_at >= week_ago)
                .group_by(func.date(ScanLog.started_at))
                .order_by("date")
                .all()
            )

            return {
                "latest_scan": {
                    "id": str(latest_scan.id) if latest_scan else None,
                    "started_at": latest_scan.started_at.isoformat()
                    if latest_scan and latest_scan.started_at
                    else None,
                    "status": latest_scan.status if latest_scan else None,
                    "new_tenders": latest_scan.new_tenders if latest_scan else 0,
                    "duration_seconds": latest_scan.duration_seconds if latest_scan else 0,
                }
                if latest_scan
                else None,
                "status_counts": dict(status_counts),
                "daily_stats": [
                    {
                        "date": stat.date.isoformat() if stat.date else None,
                        "scan_count": stat.scan_count or 0,
                        "total_new_tenders": stat.total_new_tenders or 0,
                        "avg_duration": float(stat.avg_duration) if stat.avg_duration else 0,
                    }
                    for stat in daily_stats
                ],
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error getting scan statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Email generation endpoints
class EmailGenerationRequest(BaseModel):
    tender_id: str = Field(..., description="ID of the tender to generate email for")


@app.post("/emails/generate")
async def generate_business_email(request: EmailGenerationRequest):
    """Generate and store business email for a tender"""
    try:
        from .database.models import SessionLocal, StoredTender
        from .services.ai_service import AIService

        # Get tender data from database
        db = SessionLocal()
        try:
            tender = db.query(StoredTender).filter(StoredTender.tender_id == request.tender_id).first()
            if not tender:
                raise HTTPException(status_code=404, detail="Tender not found")

            # Convert tender to dict for AI service
            tender_data = {
                "tender_id": tender.tender_id,
                "title": tender.title,
                "description": tender.description or "",
                "source": tender.source,
                "source_url": tender.source_url,
                "location": tender.location,
                "estimated_value": tender.estimated_value,
                "contact_info": tender.contact_info or {},
                "keywords_found": tender.keywords_found or [],
                "response_deadline": tender.response_deadline,
            }

        finally:
            db.close()

        # Generate and store email
        ai_service = AIService()
        email_result = await ai_service.create_and_store_business_email(tender_data)

        return {"message": "Email generated and stored successfully", "email": email_result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating business email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/emails")
async def get_all_emails(limit: int = 100):
    """Get all generated emails"""
    try:
        from .services.ai_service import AIService

        ai_service = AIService()
        emails = await ai_service.get_stored_emails(limit=limit)

        return {"emails": emails, "total_count": len(emails)}

    except Exception as e:
        logger.error(f"Error retrieving emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/emails/{tender_id}")
async def get_emails_for_tender(tender_id: str):
    """Get all emails generated for a specific tender"""
    try:
        from .services.ai_service import AIService

        ai_service = AIService()
        emails = await ai_service.get_stored_emails(tender_id=tender_id)

        return {"tender_id": tender_id, "emails": emails, "total_count": len(emails)}

    except Exception as e:
        logger.error(f"Error retrieving emails for tender {tender_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/emails/stats")
async def get_email_statistics():
    """Get email generation statistics"""
    try:
        from sqlalchemy import func

        from .database.models import GeneratedEmail, SessionLocal

        db = SessionLocal()
        try:
            # Total emails count
            total_emails = db.query(func.count(GeneratedEmail.id)).scalar()

            # Emails by status
            status_counts = (
                db.query(GeneratedEmail.status, func.count(GeneratedEmail.id)).group_by(GeneratedEmail.status).all()
            )

            # Emails by AI model
            model_counts = (
                db.query(GeneratedEmail.ai_model_used, func.count(GeneratedEmail.id))
                .group_by(GeneratedEmail.ai_model_used)
                .all()
            )

            # Recent emails (last 7 days)
            from datetime import datetime, timedelta

            week_ago = datetime.now() - timedelta(days=7)
            recent_emails = (
                db.query(func.count(GeneratedEmail.id)).filter(GeneratedEmail.generated_at >= week_ago).scalar()
            )

            return {
                "total_emails": total_emails,
                "recent_emails_7days": recent_emails,
                "status_breakdown": dict(status_counts),
                "model_breakdown": dict(model_counts),
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error getting email statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# Global storage for OAuth states and tokens (in production, use Redis)
oauth_states = {}
oauth_tokens = {}


# Load saved OAuth token on startup
def load_saved_token():
    try:
        token_file = "/tmp/autodesk_token.json"
        if os.path.exists(token_file):
            with open(token_file) as f:
                token_info = json.load(f)
                oauth_tokens["autodesk"] = token_info
                logger.info("Loaded saved OAuth token")
    except Exception as e:
        logger.warning(f"Could not load saved token: {e}")


# Load token on startup
load_saved_token()


@app.get("/auth/autodesk")
async def autodesk_auth():
    """Initiate Autodesk OAuth flow"""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = True

    auth_url = (
        f"https://developer.api.autodesk.com/authentication/v2/authorize"
        f"?response_type=code"
        f"&client_id={settings.autodesk_client_id}"
        f"&redirect_uri={urllib.parse.quote('http://69.55.55.8:8001/auth/callback')}"
        f"&scope={urllib.parse.quote('data:read data:write account:read account:write user-profile:read')}"
        f"&state={state}"
    )

    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
async def autodesk_callback(code: str, state: str):
    """Handle Autodesk OAuth callback"""
    import httpx

    if state not in oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state")

    del oauth_states[state]

    # Exchange code for token
    async with httpx.AsyncClient() as client:
        token_data = {
            "grant_type": "authorization_code",
            "client_id": settings.autodesk_client_id,
            "client_secret": settings.autodesk_client_secret,
            "code": code,
            "redirect_uri": "http://69.55.55.8:8001/auth/callback",
        }

        response = await client.post(
            "https://developer.api.autodesk.com/authentication/v2/token",
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code == 200:
            token_info = response.json()
            oauth_tokens["autodesk"] = token_info

            # Save token to file so it persists across restarts
            try:
                token_file = "/tmp/autodesk_token.json"
                with open(token_file, "w") as f:
                    json.dump(token_info, f)
                logger.info(f"OAuth token saved to {token_file}")
            except Exception as e:
                logger.error(f"Failed to save token: {e}")

            return {"status": "success", "message": "Authorization successful! You can now use ACC scraping."}
        else:
            logger.error(f"Token exchange failed: {response.text}")
            raise HTTPException(status_code=400, detail="Token exchange failed")


@app.get("/auth/status")
async def auth_status():
    """Check if user is authenticated with Autodesk"""
    return {
        "authenticated": "autodesk" in oauth_tokens,
        "token_expires": oauth_tokens.get("autodesk", {}).get("expires_in", 0),
    }


@app.get("/debug/acc")
async def debug_acc():
    """Debug ACC API access - get projects and detailed info"""
    try:
        from .services.acc_scraper import ACCClient

        client = ACCClient()

        # Test authentication
        auth_result = await client.authenticate()
        if not auth_result:
            return {"error": "Authentication failed", "auth_result": False}

        # Get projects
        projects = await client.get_projects()

        result = {
            "auth_result": auth_result,
            "access_token": client.access_token[:20] + "..." if client.access_token else None,
            "projects_count": len(projects),
            "projects": projects[:3],  # First 3 projects for debugging
        }

        # If we have projects, try to get data from first one
        if projects:
            first_project = projects[0]
            project_id = first_project.get("id")

            if project_id:
                issues = await client.get_project_issues(project_id)
                rfis = await client.get_project_rfis(project_id)
                files = await client.search_project_files(project_id, ["window", "door"])

                result["first_project_data"] = {
                    "project_id": project_id,
                    "project_name": first_project.get("attributes", {}).get("name", "Unknown"),
                    "issues_count": len(issues),
                    "rfis_count": len(rfis),
                    "files_count": len(files),
                    "sample_issues": issues[:1] if issues else [],
                    "sample_rfis": rfis[:1] if rfis else [],
                    "sample_files": files[:1] if files else [],
                }

        return result

    except Exception as e:
        logger.error(f"ACC debug error: {e}")
        return {"error": str(e), "type": type(e).__name__}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
