import asyncio
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from loguru import logger

from ..models.tender_models import ScrapingJob, ScrapingStatus, TenderSource, TenderData
from ..config import settings

class ScraperService:
    def __init__(self):
        self.jobs: Dict[str, ScrapingJob] = {}
        self.results: Dict[str, List[TenderData]] = {}
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize the scraper service"""
        logger.info("Initializing ScraperService")
        # Here you would initialize database connections, etc.
        self.is_initialized = True
        logger.info("ScraperService initialized successfully")
        
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up ScraperService")
        self.is_initialized = False
        
    async def create_job(
        self,
        source: str,
        keywords: List[str],
        filters: Dict[str, Any],
        max_results: int
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
            estimated_completion=datetime.now() + timedelta(minutes=30)
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
            
            logger.info(f"Completed scraping job {job_id}, found {len(results)} results")
            
        except Exception as e:
            logger.error(f"Error in scraping job {job_id}: {str(e)}")
            job.status = ScrapingStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()
            
    async def _scrape_source(self, job: ScrapingJob) -> List[TenderData]:
        """Scrape specific source based on job configuration"""
        results = []
        
        if job.source == TenderSource.SAM_GOV:
            results = await self._scrape_sam_gov(job)
        elif job.source == TenderSource.DODGE:
            results = await self._scrape_dodge(job)
        else:
            raise ValueError(f"Unsupported source: {job.source}")
            
        return results
        
    async def _scrape_sam_gov(self, job: ScrapingJob) -> List[TenderData]:
        """Scrape SAM.gov for tender opportunities"""
        logger.info(f"Scraping SAM.gov with keywords: {job.keywords}")
        
        # Simulate scraping delay
        await asyncio.sleep(2)
        
        # Mock data for now - will be replaced with actual Crawl4AI implementation
        mock_results = [
            TenderData(
                id=str(uuid.uuid4()),
                title=\"Window Replacement Project - Federal Building\",
                description=\"Replace all windows in federal building with energy-efficient alternatives\",
                source=TenderSource.SAM_GOV,
                source_url=\"https://sam.gov/opp/12345\",
                posting_date=datetime.now() - timedelta(days=1),
                response_deadline=datetime.now() + timedelta(days=30),
                estimated_value=150000.0,
                location=\"Washington, DC\",
                naics_codes=[\"238150\"],
                keywords_found=[\"windows\", \"replacement\"],
                relevance_score=0.85
            ),
            TenderData(
                id=str(uuid.uuid4()),
                title=\"Commercial Glazing Services\",
                description=\"Provide glazing services for new commercial construction\",
                source=TenderSource.SAM_GOV,
                source_url=\"https://sam.gov/opp/12346\",
                posting_date=datetime.now() - timedelta(hours=12),
                response_deadline=datetime.now() + timedelta(days=21),
                estimated_value=75000.0,
                location=\"New York, NY\",
                naics_codes=[\"238150\"],
                keywords_found=[\"glazing\", \"commercial\"],
                relevance_score=0.92
            )
        ]
        
        # Filter by keywords if specified
        if job.keywords:
            filtered_results = []
            for result in mock_results:
                if any(keyword.lower() in result.title.lower() or 
                      keyword.lower() in result.description.lower() 
                      for keyword in job.keywords):
                    filtered_results.append(result)
            mock_results = filtered_results
            
        # Limit results
        return mock_results[:job.max_results]
        
    async def _scrape_dodge(self, job: ScrapingJob) -> List[TenderData]:
        """Scrape Dodge Construction for tender opportunities"""
        logger.info(f"Scraping Dodge Construction with keywords: {job.keywords}")
        
        # Simulate scraping delay
        await asyncio.sleep(3)
        
        # Mock data for now
        mock_results = [
            TenderData(
                id=str(uuid.uuid4()),
                title=\"Storefront Installation - Retail Complex\",
                description=\"Install storefront windows and doors for new retail development\",
                source=TenderSource.DODGE,
                source_url=\"https://dodge.construction/project/67890\",
                posting_date=datetime.now() - timedelta(hours=6),
                response_deadline=datetime.now() + timedelta(days=14),
                estimated_value=200000.0,
                location=\"Los Angeles, CA\",
                keywords_found=[\"storefront\", \"installation\"],
                relevance_score=0.78
            )
        ]
        
        return mock_results[:job.max_results]
        
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a scraping job"""
        if job_id not in self.jobs:
            return None
            
        job = self.jobs[job_id]
        return {
            \"job_id\": job.id,
            \"status\": job.status,
            \"progress\": job.progress,
            \"results_count\": job.results_count,
            \"created_at\": job.created_at,
            \"started_at\": job.started_at,
            \"completed_at\": job.completed_at,
            \"error_message\": job.error_message
        }
        
    async def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        \"\"\"Get the results of a completed scraping job\"\"\"
        if job_id not in self.jobs or job_id not in self.results:
            return None
            
        job = self.jobs[job_id]
        results = self.results[job_id]
        
        return {
            \"tenders\": results,
            \"total_count\": len(results),
            \"job_info\": {
                \"id\": job.id,
                \"source\": job.source,
                \"keywords\": job.keywords,
                \"completed_at\": job.completed_at
            }
        }
        
    async def list_jobs(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        \"\"\"List scraping jobs with optional filters\"\"\"
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
                \"id\": job.id,
                \"source\": job.source,
                \"status\": job.status,
                \"progress\": job.progress,
                \"results_count\": job.results_count,
                \"created_at\": job.created_at,
                \"keywords\": job.keywords
            }
            for job in jobs
        ]