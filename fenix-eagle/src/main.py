import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

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


# Request/Response Models
class ScrapingRequest(BaseModel):
    source: str = Field(..., description="Scraping source (e.g., 'sam.gov', 'dodge')")
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
            raise HTTPException(
                status_code=503, detail="Scraper service not initialized"
            )

        job = await scraper_service.create_job(
            source=request.source,
            keywords=request.keywords,
            filters=request.filters,
            max_results=request.max_results,
        )

        # Start scraping in background
        background_tasks.add_task(scraper_service.execute_scraping_job, job.id)

        return ScrapingResponse(
            job_id=job.id,
            status="started",
            message=f"Scraping job started for {request.source}",
            estimated_completion=job.estimated_completion,
        )

    except Exception as e:
        logger.error(f"Error starting scraping job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrape/status/{job_id}")
async def get_scraping_status(job_id: str):
    """Get status of a scraping job"""
    try:
        if not scraper_service:
            raise HTTPException(
                status_code=503, detail="Scraper service not initialized"
            )

        status = await scraper_service.get_job_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")

        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrape/results/{job_id}", response_model=TenderResponse)
async def get_scraping_results(job_id: str):
    """Get results of a completed scraping job"""
    try:
        if not scraper_service:
            raise HTTPException(
                status_code=503, detail="Scraper service not initialized"
            )

        results = await scraper_service.get_job_results(job_id)
        if not results:
            raise HTTPException(status_code=404, detail="Results not found")

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scrape/jobs")
async def list_scraping_jobs(
    status: str | None = None, source: str | None = None, limit: int = 50
):
    """List scraping jobs with optional filters"""
    try:
        if not scraper_service:
            raise HTTPException(
                status_code=503, detail="Scraper service not initialized"
            )

        jobs = await scraper_service.list_jobs(
            status=status, source=source, limit=limit
        )

        return {"jobs": jobs, "total_count": len(jobs)}

    except Exception as e:
        logger.error(f"Error listing jobs: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Crawler endpoints
@app.post("/crawl/url")
async def crawl_url(
    url: str,
    background_tasks: BackgroundTasks,
    extract_keywords: list[str] = [],
    ai_extract: bool = True,
):
    """Crawl a specific URL using AI-powered extraction"""
    try:
        if not crawler_service:
            raise HTTPException(
                status_code=503, detail="Crawler service not initialized"
            )

        job_id = await crawler_service.crawl_url(
            url=url, extract_keywords=extract_keywords, ai_extract=ai_extract
        )

        return {
            "job_id": job_id,
            "status": "started",
            "message": f"Crawling started for {url}",
        }

    except Exception as e:
        logger.error(f"Error crawling URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
