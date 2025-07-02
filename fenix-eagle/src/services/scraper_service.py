import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from ..models.tender_models import ScrapingJob, ScrapingStatus, TenderData, TenderSource
from .crawl4ai_scraper import Crawl4AIScraper


class ScraperService:
    def __init__(self):
        self.jobs: dict[str, ScrapingJob] = {}
        self.results: dict[str, list[TenderData]] = {}
        self.is_initialized = False
        self.crawl4ai_scraper = None

    async def initialize(self):
        """Initialize the scraper service"""
        logger.info("Initializing ScraperService")

        # Initialize Crawl4AI scraper
        self.crawl4ai_scraper = Crawl4AIScraper()
        await self.crawl4ai_scraper.initialize()

        self.is_initialized = True
        logger.info("ScraperService initialized successfully")

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up ScraperService")

        # Cleanup Crawl4AI scraper
        if self.crawl4ai_scraper:
            await self.crawl4ai_scraper.cleanup()

        self.is_initialized = False

    async def create_job(
        self,
        source: str,
        keywords: list[str],
        filters: dict[str, Any],
        max_results: int,
    ) -> ScrapingJob:
        """Create a new scraping job"""
        job_id = str(uuid.uuid4())

        # Convert string source to enum
        try:
            source_enum = TenderSource(source)
        except ValueError:
            raise ValueError(f"Unsupported source: {source}")

        job = ScrapingJob(
            id=job_id,
            source=source_enum,
            keywords=keywords,
            filters=filters,
            max_results=max_results,
            estimated_completion=datetime.now() + timedelta(minutes=30),
        )

        self.jobs[job_id] = job
        logger.info(f"Created scraping job {job_id} for source {source}")

        return job

    async def execute_scraping_job(self, job_id: str):
        """Execute a scraping job in the background"""
        if job_id not in self.jobs:
            logger.error(f"Job {job_id} not found")
            return

        job = self.jobs[job_id]

        try:
            # Update job status
            job.status = ScrapingStatus.RUNNING
            job.started_at = datetime.now()
            job.progress = 10

            logger.info(f"Starting scraping job {job_id} for {job.source}")

            # Simulate scraping process
            results = await self._scrape_source(job)

            # Update job with results
            job.status = ScrapingStatus.COMPLETED
            job.completed_at = datetime.now()
            job.progress = 100
            job.results_count = len(results)

            # Store results
            self.results[job_id] = results

            logger.info(
                f"Completed scraping job {job_id}, found {len(results)} results"
            )

        except Exception as e:
            logger.error(f"Error in scraping job {job_id}: {str(e)}")
            job.status = ScrapingStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()

    async def _scrape_source(self, job: ScrapingJob) -> list[TenderData]:
        """Scrape specific source based on job configuration"""
        results = []

        if job.source == TenderSource.SAM_GOV:
            results = await self._scrape_sam_gov(job)
        elif job.source == TenderSource.DODGE:
            results = await self._scrape_dodge(job)
        else:
            raise ValueError(f"Unsupported source: {job.source}")

        return results

    async def _scrape_sam_gov(self, job: ScrapingJob) -> list[TenderData]:
        """Scrape SAM.gov for tender opportunities using Crawl4AI"""
        logger.info(f"Scraping SAM.gov with keywords: {job.keywords}")

        try:
            if self.crawl4ai_scraper:
                # Use real Crawl4AI scraping
                results = await self.crawl4ai_scraper.scrape_sam_gov(
                    keywords=job.keywords, max_results=job.max_results
                )
                logger.info(f"Crawl4AI returned {len(results)} results")
                return results
            else:
                logger.error("Crawl4AI scraper not available")
                return []

        except Exception as e:
            logger.error(f"Error in SAM.gov scraping: {e}")
            return []

    async def _scrape_dodge(self, job: ScrapingJob) -> list[TenderData]:
        """Scrape Dodge Construction for tender opportunities"""
        logger.info(f"Scraping Dodge Construction with keywords: {job.keywords}")

        # Simulate scraping delay
        await asyncio.sleep(3)

        # Mock data for now
        mock_results = [
            TenderData(
                id=str(uuid.uuid4()),
                title="Storefront Installation - Retail Complex",
                description="Install storefront windows and doors for new retail development",
                source=TenderSource.DODGE,
                source_url="https://dodge.construction/project/67890",
                posting_date=datetime.now() - timedelta(hours=6),
                response_deadline=datetime.now() + timedelta(days=14),
                estimated_value=200000.0,
                location="Los Angeles, CA",
                keywords_found=["storefront", "installation"],
                relevance_score=0.78,
            )
        ]

        return mock_results[: job.max_results]

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get the status of a scraping job"""
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]
        return {
            "job_id": job.id,
            "status": job.status,
            "progress": job.progress,
            "results_count": job.results_count,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
        }

    async def get_job_results(self, job_id: str) -> dict[str, Any] | None:
        """Get the results of a completed scraping job"""
        if job_id not in self.jobs or job_id not in self.results:
            return None

        job = self.jobs[job_id]
        results = self.results[job_id]

        return {
            "tenders": results,
            "total_count": len(results),
            "job_info": {
                "id": job.id,
                "source": job.source,
                "keywords": job.keywords,
                "completed_at": job.completed_at,
            },
        }

    async def list_jobs(
        self, status: str | None = None, source: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List scraping jobs with optional filters"""
        jobs = list(self.jobs.values())

        # Filter by status
        if status:
            jobs = [job for job in jobs if job.status == status]

        # Filter by source
        if source:
            jobs = [job for job in jobs if job.source == source]

        # Sort by creation date (newest first)
        jobs.sort(key=lambda x: x.created_at, reverse=True)

        # Limit results
        jobs = jobs[:limit]

        # Convert to dict format
        return [
            {
                "id": job.id,
                "source": job.source,
                "status": job.status,
                "progress": job.progress,
                "results_count": job.results_count,
                "created_at": job.created_at,
                "keywords": job.keywords,
            }
            for job in jobs
        ]
