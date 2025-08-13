import asyncio
import logging
from typing import Any

import aiohttp


logger = logging.getLogger(__name__)


class EagleServiceClient:
    """HTTP client for communicating with Eagle service from scheduler"""

    def __init__(self, eagle_base_url: str = "http://eagle:8001"):
        self.eagle_base_url = eagle_base_url
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def health_check(self) -> bool:
        """Check if Eagle service is healthy"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

            async with self.session.get(f"{self.eagle_base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Eagle service health check failed: {e}")
            return False

    async def create_scraping_job(
        self,
        source: str,
        keywords: list[str],
        max_results: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Create a scraping job via Eagle service API"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

            payload = {
                "source": source,
                "keywords": keywords,
                "max_results": max_results,
                "filters": filters or {},
            }

            async with self.session.post(f"{self.eagle_base_url}/scrape/start", json=payload) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    text = await response.text()
                    logger.error(f"Failed to create job: {response.status} - {text}")
                    return None
        except Exception as e:
            logger.error(f"Error creating scraping job: {e}")
            return None

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Get job status via Eagle service API"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

            async with self.session.get(f"{self.eagle_base_url}/scrape/status/{job_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get job status: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None

    async def get_job_results(self, job_id: str) -> dict[str, Any] | None:
        """Get job results via Eagle service API"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

            async with self.session.get(f"{self.eagle_base_url}/scrape/results/{job_id}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get job results: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting job results: {e}")
            return None

    async def wait_for_job_completion(
        self, job_id: str, timeout: int = 600, poll_interval: int = 2
    ) -> dict[str, Any] | None:
        """Wait for job completion with proper polling"""
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                logger.error(f"Job {job_id} timed out after {timeout} seconds")
                return None

            job_status = await self.get_job_status(job_id)
            if not job_status:
                logger.error(f"Could not get status for job {job_id}")
                return None

            status = job_status.get("status")

            if status == "completed":
                logger.info(f"Job {job_id} completed successfully")
                return job_status
            elif status == "failed":
                error_msg = job_status.get("error_message", "Unknown error")
                logger.error(f"Job {job_id} failed: {error_msg}")
                return job_status

            # Still in progress, wait and retry
            await asyncio.sleep(poll_interval)

    async def cleanup(self) -> None:
        """Clean up HTTP session if it exists"""
        if self.session and not self.session.closed:
            await self.session.close()
