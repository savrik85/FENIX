import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlencode

from loguru import logger


try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import LLMExtractionStrategy

    CRAWL4AI_AVAILABLE = True
except ImportError:
    logger.warning("Crawl4AI not available, using fallback scraping")
    CRAWL4AI_AVAILABLE = False

import aiohttp
from bs4 import BeautifulSoup

from ..config import settings
from ..models.tender_models import TenderData, TenderSource


class Crawl4AIScraper:
    """Real Crawl4AI-based scraper for government contracting opportunities"""

    def __init__(self):
        self.crawler = None
        self.session = None

    async def initialize(self):
        """Initialize the Crawl4AI scraper"""
        logger.info("Initializing Crawl4AI scraper")

        if CRAWL4AI_AVAILABLE:
            try:
                self.crawler = AsyncWebCrawler(verbose=True)
                await self.crawler.start()
                logger.info("Crawl4AI initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Crawl4AI: {e}")
                self.crawler = None

        # Initialize HTTP session for fallback
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            },
        )

    async def cleanup(self):
        """Cleanup resources"""
        if self.crawler:
            await self.crawler.close()
        if self.session:
            await self.session.close()

    async def scrape_sam_gov(self, keywords: list[str], max_results: int = 100) -> list[TenderData]:
        """Scrape SAM.gov for contracting opportunities using API-first approach"""
        logger.info(f"Starting SAM.gov API scraping with keywords: {keywords}")

        try:
            # Build API URL - prioritize direct API access
            api_url = self._build_sam_gov_url(keywords, max_results)
            logger.info(f"SAM.gov API URL: {api_url}")

            # Try direct API access first (fastest and most reliable)
            try:
                return await self._scrape_sam_gov_api_direct(api_url, keywords)
            except Exception as e:
                logger.warning(f"Direct API access failed: {e}")

                # Fallback to Crawl4AI only if API fails and AI processing is needed
                if self.crawler and CRAWL4AI_AVAILABLE:
                    logger.info("Trying Crawl4AI as fallback for enhanced data extraction")
                    return await self._scrape_with_crawl4ai(api_url, keywords)
                else:
                    logger.error("Crawl4AI not available and API failed")
                    raise Exception("Both direct API and Crawl4AI failed") from e

        except Exception as e:
            logger.error(f"All SAM.gov scraping methods failed: {e}")
            # Return empty list instead of mock data
            return []

    async def scrape_construction_com(self, keywords: list[str], max_results: int = 100) -> list[TenderData]:
        """Scrape Construction.com using Crawl4AI for construction opportunities"""
        logger.info(f"Starting Construction.com scraping with keywords: {keywords}")

        try:
            # Build search URL for Construction.com
            search_url = self._build_construction_com_url(keywords, max_results)
            logger.info(f"Construction.com search URL: {search_url}")

            # Use Crawl4AI for intelligent extraction
            if self.crawler and CRAWL4AI_AVAILABLE:
                return await self._scrape_construction_com_with_crawl4ai(search_url, keywords)
            else:
                logger.error("Crawl4AI not available for Construction.com scraping")
                return []

        except Exception as e:
            logger.error(f"Construction.com scraping failed: {e}")
            return []

    def _build_sam_gov_url(self, keywords: list[str], max_results: int) -> str:
        """Build SAM.gov search URL with keywords"""
        base_url = "https://sam.gov/api/prod/opportunities/v2/search"

        # Combine keywords into search query with OR logic for better matches
        query = " OR ".join([f'"{keyword}"' for keyword in keywords])

        params = {
            "api_key": settings.sam_gov_api_key,
            "q": query,
            "size": min(max_results, 100),  # SAM.gov API limit
            "postedFrom": (datetime.now() - timedelta(days=14)).strftime("%m/%d/%Y"),
            "postedTo": datetime.now().strftime("%m/%d/%Y"),
            "ptype": "o",  # Opportunities only
        }

        return f"{base_url}?{urlencode(params)}"

    def _build_construction_com_url(self, keywords: list[str], max_results: int) -> str:
        """Build Construction.com search URL with keywords"""
        base_url = "https://www.construction.com/projects"

        # Combine keywords for search
        query = " ".join(keywords)

        params = {
            "q": query,
            "limit": min(max_results, 50),  # Construction.com reasonable limit
            "sort": "posted_date",
            "order": "desc",
        }

        return f"{base_url}?{urlencode(params)}"

    async def _scrape_sam_gov_api_direct(self, url: str, keywords: list[str]) -> list[TenderData]:
        """Direct API access to SAM.gov - fastest method"""
        logger.info("Using direct SAM.gov API access")

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"API returned status {response.status}")

                content = await response.text()
                data = json.loads(content)

                # Check if response is valid
                if "opportunitiesData" not in data and "results" not in data:
                    raise Exception("Invalid API response structure")

                results = self._parse_sam_gov_api_response(data, keywords)
                logger.info(f"Direct API access returned {len(results)} opportunities")
                return results

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse API JSON response: {e}") from e
        except Exception as e:
            raise Exception(f"Direct API access error: {e}") from e

    async def _scrape_with_crawl4ai(self, url: str, keywords: list[str]) -> list[TenderData]:
        """Scrape using Crawl4AI with AI extraction"""
        logger.info("Using Crawl4AI for intelligent scraping")

        try:
            # Define extraction strategy for government contracts
            extraction_strategy = LLMExtractionStrategy(
                provider="openai/gpt-4o-mini",
                api_token=settings.openai_api_key,
                schema={
                    "type": "object",
                    "properties": {
                        "opportunities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "solicitation_number": {"type": "string"},
                                    "agency": {"type": "string"},
                                    "office": {"type": "string"},
                                    "posted_date": {"type": "string"},
                                    "response_deadline": {"type": "string"},
                                    "estimated_value": {"type": "string"},
                                    "location": {"type": "string"},
                                    "naics_codes": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                    "contact_info": {"type": "string"},
                                    "set_aside": {"type": "string"},
                                    "opportunity_url": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                instruction="""
                Extract government contracting opportunities from this page.
                Focus on opportunities related to construction, windows, doors,
                glazing, and fenestration.
                For each opportunity, extract all available details including:
                - Title and description
                - Solicitation/opportunity number
                - Agency and office information
                - Important dates (posted date, response deadline)
                - Estimated contract value
                - Location/place of performance
                - NAICS codes if available
                - Contact information
                - Set-aside information (small business, etc.)
                - Direct URL to the opportunity

                Return structured data that can be easily processed.
                """,
            )

            # Crawl with AI extraction
            result = await self.crawler.run(
                url=url,
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                js_code="window.scrollTo(0, document.body.scrollHeight);",
                wait_for="body",
            )

            if result.extracted_content:
                extracted_data = json.loads(result.extracted_content)
                return self._convert_to_tender_data(extracted_data.get("opportunities", []), keywords)
            else:
                logger.warning("No content extracted with Crawl4AI")
                return []

        except Exception as e:
            logger.error(f"Crawl4AI extraction failed: {e}")
            return []

    async def _scrape_construction_com_with_crawl4ai(self, url: str, keywords: list[str]) -> list[TenderData]:
        """Scrape Construction.com using Crawl4AI with construction-specific
        extraction"""
        logger.info("Using Crawl4AI for Construction.com intelligent scraping")

        try:
            # Define extraction strategy for construction projects
            extraction_strategy = LLMExtractionStrategy(
                provider="openai/gpt-4o-mini",
                api_token=settings.openai_api_key,
                schema={
                    "type": "object",
                    "properties": {
                        "projects": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "project_id": {"type": "string"},
                                    "owner": {"type": "string"},
                                    "contractor": {"type": "string"},
                                    "architect": {"type": "string"},
                                    "posted_date": {"type": "string"},
                                    "bid_date": {"type": "string"},
                                    "estimated_value": {"type": "string"},
                                    "location": {"type": "string"},
                                    "project_type": {"type": "string"},
                                    "project_stage": {"type": "string"},
                                    "contact_info": {"type": "string"},
                                    "project_url": {"type": "string"},
                                    "specifications": {"type": "string"},
                                },
                            },
                        }
                    },
                },
                instruction="""
                Extract construction project opportunities from this
                Construction.com page.
                Focus on projects that involve windows, doors, glazing,
                facades, or building envelope work.
                For each project, extract all available details including:
                - Project title and description
                - Project ID or reference number
                - Owner/client information
                - General contractor if listed
                - Architect/engineer information
                - Important dates (posting date, bid date, start date)
                - Estimated project value or budget
                - Location/address of the project
                - Project type (commercial, residential, institutional, etc.)
                - Project stage (planning, bidding, construction, etc.)
                - Contact information for inquiries
                - Direct URL to the project details
                - Key specifications related to fenestration/glazing

                Look for keywords like: windows, doors, glazing, curtain wall,
                storefront,
                facade, exterior, envelope, fenestration, glass, aluminum, installation.

                Return structured data for easy processing.
                """,
            )

            # Crawl with AI extraction
            result = await self.crawler.run(
                url=url,
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                js_code="""
                // Scroll to load more content
                window.scrollTo(0, document.body.scrollHeight);

                // Wait for dynamic content
                await new Promise(resolve => setTimeout(resolve, 2000));

                // Try to click "Load More" or "Show More" buttons if they exist
                const loadMoreButtons = document.querySelectorAll(
                    '[data-testid="load-more"], .load-more, .show-more, .view-more'
                );
                loadMoreButtons.forEach(button => {
                    if (button.offsetParent !== null) {
                        button.click();
                    }
                });

                await new Promise(resolve => setTimeout(resolve, 1000));
                """,
                wait_for="body",
                timeout=60000,  # Longer timeout for construction sites
            )

            if result.extracted_content:
                extracted_data = json.loads(result.extracted_content)
                return self._convert_construction_com_to_tender_data(extracted_data.get("projects", []), keywords)
            else:
                logger.warning("No content extracted from Construction.com with Crawl4AI")
                return []

        except Exception as e:
            logger.error(f"Construction.com Crawl4AI extraction failed: {e}")
            return []

    async def scrape_nyc_opendata(self, keywords: list[str], max_results: int = 100) -> list[TenderData]:
        """Scrape NYC Open Data for building permits using DOB Job
        Application Filings API"""
        logger.info(f"Starting NYC DOB scraping with keywords: {keywords}")

        try:
            # NYC DOB Job Application Filings API endpoint
            api_url = "https://data.cityofnewyork.us/resource/ic3t-wcy2.json"

            # Build query for recent A1/A2 type jobs (alterations most
            # likely to have windows)

            # Get jobs without date filter to ensure we get data
            params = {
                "$limit": min(max_results * 5, 1000),  # Get more to filter locally
                "$order": "latest_action_date DESC",
                "$where": "job_type IN('A1','A2')",
            }

            logger.info(f"NYC DOB API URL: {api_url}")
            logger.info(f"NYC DOB API params: {params}")

            async with self.session.get(api_url, params=params) as response:
                if response.status != 200:
                    raise Exception(f"NYC DOB API returned status {response.status}")

                data = await response.json()
                logger.info(f"NYC DOB API returned {len(data)} job applications")

                # Convert NYC DOB data to TenderData
                return self._convert_nyc_dob_to_tender_data(data, keywords, max_results)

        except Exception as e:
            logger.error(f"NYC DOB API scraping failed: {e}")
            return []

    def _convert_nyc_dob_to_tender_data(
        self, jobs: list[dict], keywords: list[str], max_results: int
    ) -> list[TenderData]:
        """Convert NYC DOB Job Application data to TenderData format"""
        logger.info(f"Converting {len(jobs)} NYC DOB job applications to TenderData")

        tenders = []
        for job in jobs:
            try:
                # Extract job details
                job_number = job.get("job__", "")
                job_type = job.get("job_type", "")
                job_status = job.get("job_status_descrp", "")

                # Build title from job type and status
                work_type = job.get("work_type", "")
                title = f"{job_type} Application - {work_type}" if work_type else f"{job_type} Application"

                # Build description from available fields
                building_type = job.get("building_type", "")
                description_parts = []
                if job_status:
                    description_parts.append(f"Status: {job_status}")
                if building_type:
                    description_parts.append(f"Building Type: {building_type}")
                if work_type:
                    description_parts.append(f"Work Type: {work_type}")

                description = "\n".join(description_parts)

                # Parse dates
                action_date = self._parse_date(job.get("latest_action_date"))

                # Build location
                house_no = job.get("house__", "")
                street = job.get("street_name", "")
                borough = job.get("borough", "")
                location = f"{house_no} {street}, {borough}".strip()

                # Calculate relevance based on work type and building type
                full_text = f"{title} {description} {work_type} {building_type}"
                relevance_score = self._calculate_dob_relevance(full_text, keywords)

                # Build job URL
                job_url = f"https://a810-bisweb.nyc.gov/bisweb/JobsQueryByNumberServlet?requestid=1&passjobnumber={job_number}"

                # Extract applicant info
                applicant_name = (
                    f"{job.get('applicant_s_first_name', '')} {job.get('applicant_s_last_name', '')}"
                ).strip()
                applicant_title = job.get("applicant_professional_title", "")
                applicant_license = job.get("applicant_license__", "")

                tender = TenderData(
                    id=str(uuid.uuid4()),
                    title=title or f"DOB Job #{job_number}",
                    description=description[:1000],
                    source=TenderSource.NYC_OPEN_DATA,
                    source_url=job_url,
                    posting_date=action_date or datetime.now(),
                    response_deadline=None,  # DOB jobs don't have deadlines
                    estimated_value=None,  # Not available in this dataset
                    location=location,
                    naics_codes=[],
                    keywords_found=self._find_keywords_in_text(full_text, keywords),
                    relevance_score=relevance_score,
                    contact_info={
                        "applicant_name": applicant_name,
                        "applicant_title": applicant_title,
                        "applicant_license": applicant_license,
                        "borough": borough,
                    },
                    requirements=[],
                    extracted_data={
                        "job_number": job_number,
                        "job_type": job_type,
                        "job_status": job_status,
                        "work_type": work_type,
                        "building_type": building_type,
                        "borough": borough,
                        "block": job.get("block", ""),
                        "lot": job.get("lot", ""),
                        "bin": job.get("bin__", ""),
                        "zoning_dist1": job.get("zoning_dist1", ""),
                        "gis_latitude": job.get("gis_latitude", ""),
                        "gis_longitude": job.get("gis_longitude", ""),
                        "raw_data": job,
                    },
                )

                # Only add if relevance score meets threshold
                min_relevance = float(os.getenv("MIN_RELEVANCE_SCORE", "0.3"))
                if relevance_score >= min_relevance:
                    tenders.append(tender)

            except Exception as e:
                logger.error(f"Error converting NYC DOB job: {e}")
                continue

        # Sort by relevance score (highest first) and limit results
        tenders.sort(key=lambda t: t.relevance_score or 0, reverse=True)
        result = tenders[:max_results]

        logger.info(f"Successfully converted {len(result)} relevant NYC DOB jobs")
        return result

    async def scrape_shovels_ai(self, keywords: list[str], max_results: int = 100) -> list[TenderData]:
        """Scrape Shovels AI for building permits and contractor data"""
        logger.info(f"Starting Shovels AI API scraping with keywords: {keywords}")

        if not settings.shovels_ai_api_key:
            logger.error("Shovels AI API key not configured")
            return []

        try:
            # Shovels AI API base URL
            api_url = "https://api.shovels.ai/v2/permits/search"

            # Build search query - try empty query if keywords don't work
            search_query = " ".join(keywords) if keywords else ""

            headers = {
                "X-API-Key": settings.shovels_ai_api_key,
                "Content-Type": "application/json",
            }

            # Search parameters for window/door/glazing permits
            # Calculate date range (last 90 days) - use correct field names
            # for broader search
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

            params = {
                "q": search_query,
                "size": min(max_results, 100),  # Use 'size' instead of 'limit'
                "start_date": start_date,  # Required field (documentation)
                "end_date": end_date,  # Required field (documentation)
                "permit_from": start_date,  # Required field (API error)
                "permit_to": end_date,  # Required field (API error)
                "geo_id": "BBRgb3iYiwY",  # Los Angeles, CA (obtained via
                # address search)
            }

            logger.info(f"Shovels AI API params: {params}")
            logger.info(f"Shovels AI API URL: {api_url}")

            async with self.session.get(api_url, headers=headers, params=params) as response:
                if response.status == 401:
                    logger.error("Shovels AI API authentication failed - check API key")
                    return []
                elif response.status != 200:
                    try:
                        error_text = await response.text()
                        logger.error(f"Shovels AI API returned status {response.status}: {error_text}")
                    except Exception as e:
                        logger.error(f"Shovels AI API returned status {response.status}, error reading response: {e}")
                    return []

                data = await response.json()
                permits = data.get("permits", [])
                logger.info(f"Shovels AI returned {len(permits)} permits")
                logger.info(f"Shovels AI raw response: {data}")

                # Convert Shovels AI data to TenderData
                return self._convert_shovels_permits_to_tender_data(permits, keywords)

        except Exception as e:
            logger.error(f"Shovels AI API scraping failed: {e}")
            return []

    def _convert_shovels_permits_to_tender_data(self, permits: list[dict], keywords: list[str]) -> list[TenderData]:
        """Convert Shovels AI permit data to TenderData format"""
        logger.info(f"Converting {len(permits)} Shovels AI permits to TenderData")

        tenders = []
        for permit in permits:
            try:
                # Extract permit details
                permit_id = permit.get("id", "")
                permit_number = permit.get("number", "")

                # Build title from type and subtype
                permit_type = permit.get("type", "")
                permit_subtype = permit.get("subtype", "")
                title = f"{permit_type} - {permit_subtype}" if permit_subtype else permit_type

                # Get description from work description
                description = permit.get("work_description", "")

                # Get contractor info
                contractor = permit.get("contractor", {})
                contractor_name = contractor.get("name", "")
                contractor_license = contractor.get("license_number", "")

                # Parse dates
                filed_date = self._parse_date(permit.get("filed_date"))
                # issued_date = self._parse_date(permit.get("issued_date"))
                # completed_date = self._parse_date(permit.get("completed_date"))

                # Get location
                address = permit.get("address", {})
                location = (
                    f"{address.get('street', '')} {address.get('city', '')} "
                    f"{address.get('state', '')} {address.get('zip', '')}"
                ).strip()

                # Get value
                estimated_value = permit.get("estimated_cost")

                # Calculate relevance
                work_desc = description.lower()
                relevance_score = self._calculate_relevance(title, work_desc, keywords)

                # Build permit URL (if available)
                permit_url = permit.get("url", f"https://api.shovels.ai/permits/{permit_id}")

                tender = TenderData(
                    id=str(uuid.uuid4()),
                    title=title or f"Permit #{permit_number}",
                    description=description[:1000],
                    source=TenderSource.SHOVELS_AI,
                    source_url=permit_url,
                    posting_date=filed_date or datetime.now(),
                    response_deadline=None,  # Permits don't have deadlines
                    estimated_value=estimated_value,
                    location=location,
                    naics_codes=[],
                    keywords_found=self._find_keywords_in_text(work_desc, keywords),
                    relevance_score=relevance_score,
                    contact_info={
                        "contractor": contractor_name,
                        "contractor_license": contractor_license,
                        "contractor_id": contractor.get("id", ""),
                    },
                    requirements=[],
                    extracted_data={
                        "permit_id": permit_id,
                        "permit_number": permit_number,
                        "permit_type": permit_type,
                        "permit_subtype": permit_subtype,
                        "status": permit.get("status", ""),
                        "filed_date": permit.get("filed_date"),
                        "issued_date": permit.get("issued_date"),
                        "completed_date": permit.get("completed_date"),
                        "inspections": permit.get("inspections", []),
                        "jurisdiction": permit.get("jurisdiction", {}),
                        "geo_id": permit.get("geo_id", ""),
                        "raw_data": permit,
                    },
                )

                # Add all permits with window/door/glass keywords
                if relevance_score > 0.2:
                    tenders.append(tender)

            except Exception as e:
                logger.error(f"Error converting Shovels AI permit: {e}")
                continue

        logger.info(f"Successfully converted {len(tenders)} relevant Shovels AI permits")
        return tenders

    def _parse_sam_gov_api_response(self, data: dict, keywords: list[str]) -> list[TenderData]:
        """Parse SAM.gov API JSON response"""
        logger.info("Parsing SAM.gov API response")

        opportunities = []

        # Navigate the API response structure
        results = data.get("opportunitiesData", [])
        if not results:
            results = data.get("results", [])

        for item in results:
            try:
                # Extract opportunity data
                title = item.get("title", item.get("solicitation_title", "Unknown Title"))
                description = item.get("description", item.get("solicitation_description", ""))

                # Parse dates
                posted_date = self._parse_date(item.get("postedDate", item.get("posted_date")))
                response_deadline = self._parse_date(item.get("responseDeadLine", item.get("response_deadline")))

                # Build opportunity URL
                solicitation_number = item.get("solicitationNumber", item.get("solicitation_number", ""))
                opportunity_url = (
                    f"https://sam.gov/opp/{solicitation_number}" if solicitation_number else "https://sam.gov"
                )

                # Calculate relevance score
                relevance_score = self._calculate_relevance(title, description, keywords)

                tender = TenderData(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description[:1000],  # Limit description length
                    source=TenderSource.SAM_GOV,
                    source_url=opportunity_url,
                    posting_date=posted_date,
                    response_deadline=response_deadline,
                    estimated_value=self._parse_value(item.get("estimatedValue", item.get("estimated_value"))),
                    location=self._extract_location(item.get("placeOfPerformance", item.get("location", ""))),
                    naics_codes=self._extract_naics_codes(item),
                    keywords_found=self._find_keywords_in_text(title + " " + description, keywords),
                    relevance_score=relevance_score,
                    contact_info=self._extract_contact_info(item),
                    requirements=[],
                    extracted_data={
                        "agency": item.get("department", item.get("agency", "")),
                        "office": item.get("subTier", item.get("office", "")),
                        "solicitation_number": solicitation_number,
                        "set_aside": item.get("typeOfSetAside", ""),
                        "raw_data": item,
                    },
                )

                opportunities.append(tender)

            except Exception as e:
                logger.error(f"Error parsing opportunity: {e}")
                continue

        logger.info(f"Parsed {len(opportunities)} opportunities from SAM.gov API")
        return opportunities

    def _parse_html_content(self, html: str, keywords: list[str]) -> list[TenderData]:
        """Parse HTML content using BeautifulSoup"""
        logger.info("Parsing HTML content")

        soup = BeautifulSoup(html, "html.parser")
        opportunities = []

        # Look for common opportunity containers
        opportunity_selectors = [
            ".opportunity-item",
            ".search-result",
            '[data-testid="opportunity"]',
            ".opp-item",
        ]

        for selector in opportunity_selectors:
            items = soup.select(selector)
            if items:
                logger.info(f"Found {len(items)} opportunities with selector: {selector}")
                break

        if not items:
            # Fallback: look for any element containing opportunity-like text
            items = soup.find_all(
                text=lambda text: text and any(keyword.lower() in text.lower() for keyword in keywords)
            )
            logger.info(f"Fallback: found {len(items)} text matches")

        for item in items[:10]:  # Limit to 10 results
            try:
                # Extract text content
                if hasattr(item, "get_text"):
                    text = item.get_text(strip=True)
                else:
                    text = str(item).strip()

                if len(text) < 50:  # Skip short text
                    continue

                # Try to extract a proper SAM.gov URL from the HTML element
                source_url = self._extract_sam_gov_url_from_element(item)

                # Create basic tender data
                tender = TenderData(
                    id=str(uuid.uuid4()),
                    title=text[:100] + "..." if len(text) > 100 else text,
                    description=text[:500] + "..." if len(text) > 500 else text,
                    source=TenderSource.SAM_GOV,
                    source_url=source_url,
                    posting_date=datetime.now(),
                    response_deadline=datetime.now() + timedelta(days=30),
                    estimated_value=None,
                    location="",
                    naics_codes=[],
                    keywords_found=self._find_keywords_in_text(text, keywords),
                    relevance_score=self._calculate_relevance(text, "", keywords),
                    contact_info={},
                    requirements=[],
                    extracted_data={"raw_html": text},
                )

                opportunities.append(tender)

            except Exception as e:
                logger.error(f"Error parsing HTML item: {e}")
                continue

        logger.info(f"Parsed {len(opportunities)} opportunities from HTML")
        return opportunities

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse date string to datetime"""
        if not date_str:
            return None

        try:
            # Try different date formats
            for fmt in [
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
            ]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def _parse_value(self, value_str: str | None) -> float | None:
        """Parse estimated value string to float"""
        if not value_str:
            return None

        try:
            # Remove currency symbols and commas
            clean_value = str(value_str).replace("$", "").replace(",", "").replace(" ", "")
            return float(clean_value)
        except (ValueError, TypeError):
            return None

    def _extract_naics_codes(self, item: dict) -> list[str]:
        """Extract NAICS codes from opportunity data"""
        naics_fields = ["naicsCode", "naics_code", "naicsCodes", "naics_codes"]

        for field in naics_fields:
            value = item.get(field)
            if value:
                if isinstance(value, list):
                    return [str(code) for code in value]
                else:
                    return [str(value)]

        return []

    def _extract_contact_info(self, item: dict) -> dict[str, Any]:
        """Extract contact information"""
        contact_fields = {
            "email": ["contactEmail", "contact_email", "email"],
            "phone": ["contactPhone", "contact_phone", "phone"],
            "name": ["contactName", "contact_name", "contact"],
        }

        contact_info = {}
        for field, possible_keys in contact_fields.items():
            for key in possible_keys:
                if key in item and item[key]:
                    contact_info[field] = item[key]
                    break

        return contact_info

    def _find_keywords_in_text(self, text: str, keywords: list[str]) -> list[str]:
        """Find which keywords appear in the text"""
        text_lower = text.lower()
        found = []

        for keyword in keywords:
            if keyword.lower() in text_lower:
                found.append(keyword)

        return found

    def _calculate_relevance(self, title: str, description: str, keywords: list[str]) -> float:
        """Calculate relevance score based on keyword matches"""
        text = f"{title} {description}".lower()

        # Base score
        score = 0.3

        # Keyword matches
        for keyword in keywords:
            if keyword.lower() in text:
                # Title matches are worth more
                if keyword.lower() in title.lower():
                    score += 0.3
                else:
                    score += 0.2

        # Industry-specific terms boost
        industry_terms = [
            "window",
            "door",
            "glazing",
            "fenestration",
            "curtain wall",
            "storefront",
        ]
        for term in industry_terms:
            if term in text:
                score += 0.1

        return min(score, 1.0)  # Cap at 1.0

    def _calculate_dob_relevance(self, text: str, keywords: list[str]) -> float:
        """Calculate relevance score specifically for NYC DOB jobs"""
        text_lower = text.lower()

        # Base score for construction work
        score = 0.2

        # Keyword matches
        for keyword in keywords:
            if keyword.lower() in text_lower:
                score += 0.25

        # DOB-specific high-relevance terms
        dob_terms = {
            "window": 0.4,
            "door": 0.3,
            "glazing": 0.5,
            "glass": 0.3,
            "storefront": 0.5,
            "curtain wall": 0.5,
            "facade": 0.4,
            "fenestration": 0.5,
            "renovation": 0.3,
            "alteration": 0.3,
            "interior": 0.2,
            "construction": 0.2,
            "installation": 0.3,
            "replacement": 0.3,
            "repair": 0.2,
            "modification": 0.2,
        }

        for term, boost in dob_terms.items():
            if term in text_lower:
                score += boost

        # Penalize obviously irrelevant work
        penalty_terms = [
            "plumbing",
            "electrical",
            "hvac",
            "roofing",
            "demolition",
            "sidewalk",
            "scaffold",
            "sprinkler",
            "elevator",
            "boiler",
        ]
        for term in penalty_terms:
            if term in text_lower:
                score -= 0.2

        return max(0.0, min(score, 1.0))

    def _convert_construction_com_to_tender_data(self, projects: list[dict], keywords: list[str]) -> list[TenderData]:
        """Convert Construction.com project data to TenderData format"""
        logger.info(f"Converting {len(projects)} Construction.com projects to TenderData")

        tenders = []
        for project in projects:
            try:
                # Parse dates
                posted_date = self._parse_date(project.get("posted_date"))
                bid_date = self._parse_date(project.get("bid_date"))

                # Build project URL
                project_url = project.get("project_url", "https://www.construction.com")
                if not project_url.startswith("http"):
                    project_url = f"https://www.construction.com{project_url}"

                # Extract and parse value
                estimated_value = self._parse_value(project.get("estimated_value"))

                # Calculate relevance
                title = project.get("title", "")
                description = project.get("description", "")
                specs = project.get("specifications", "")
                full_text = f"{title} {description} {specs}"

                relevance_score = self._calculate_relevance(title, description, keywords)

                # Extract contact info
                contact_raw = project.get("contact_info", "")
                contact_info = self._parse_construction_contact_info(contact_raw)

                tender = TenderData(
                    id=str(uuid.uuid4()),
                    title=title or "Construction Project",
                    description=(description + f"\n\nSpecifications: {specs}")[:1000],
                    source=TenderSource.CONSTRUCTION_COM,
                    source_url=project_url,
                    posting_date=posted_date or datetime.now(),
                    response_deadline=bid_date,
                    estimated_value=estimated_value,
                    location=project.get("location", ""),
                    naics_codes=[],  # Construction.com doesn't typically provide NAICS
                    keywords_found=self._find_keywords_in_text(full_text, keywords),
                    relevance_score=relevance_score,
                    contact_info=contact_info,
                    requirements=[],
                    extracted_data={
                        "project_id": project.get("project_id", ""),
                        "owner": project.get("owner", ""),
                        "contractor": project.get("contractor", ""),
                        "architect": project.get("architect", ""),
                        "project_type": project.get("project_type", ""),
                        "project_stage": project.get("project_stage", ""),
                        "specifications": specs,
                        "raw_data": project,
                    },
                )

                tenders.append(tender)

            except Exception as e:
                logger.error(f"Error converting Construction.com project: {e}")
                continue

        logger.info(f"Successfully converted {len(tenders)} Construction.com projects")
        return tenders

    def _parse_construction_contact_info(self, contact_raw: str) -> dict[str, Any]:
        """Parse contact information from Construction.com format"""
        contact_info = {}

        if not contact_raw:
            return contact_info

        # Try to extract email using regex
        import re

        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        emails = re.findall(email_pattern, contact_raw)
        if emails:
            contact_info["email"] = emails[0]

        # Try to extract phone using regex
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        phones = re.findall(phone_pattern, contact_raw)
        if phones:
            contact_info["phone"] = phones[0]

        # Store raw contact info
        contact_info["raw"] = contact_raw.strip()

        return contact_info

    def _extract_location(self, location_data) -> str:
        """Extract location string from complex location data"""
        if isinstance(location_data, str):
            return location_data
        elif isinstance(location_data, dict):
            # Handle complex location objects from SAM.gov API
            parts = []
            if "city" in location_data:
                parts.append(location_data["city"].get("name", ""))
            if "state" in location_data:
                parts.append(location_data["state"].get("code", ""))
            if "country" in location_data:
                country_name = location_data["country"].get("name", "")
                if country_name and country_name != "UNITED STATES":
                    parts.append(country_name)
            return ", ".join(filter(None, parts))
        else:
            return str(location_data) if location_data else ""

    def _extract_sam_gov_url_from_element(self, element) -> str:
        """Extract proper SAM.gov URL from HTML element"""
        try:
            # If element is a BeautifulSoup element
            if hasattr(element, "find"):
                # Look for links within the element
                links = element.find_all("a", href=True)
                for link in links:
                    href = link["href"]
                    if "sam.gov" in href and "/opp/" in href:
                        # Found a direct SAM.gov opportunity link
                        if href.startswith("http"):
                            return href
                        else:
                            return f"https://sam.gov{href}" if href.startswith("/") else f"https://sam.gov/{href}"

                # Look for solicitation numbers in the text or data attributes
                text_content = element.get_text() if hasattr(element, "get_text") else str(element)
                solicitation_match = self._extract_solicitation_number_from_text(text_content)
                if solicitation_match:
                    return f"https://sam.gov/opp/{solicitation_match}"

                # Check for data attributes that might contain URLs or IDs
                if hasattr(element, "get"):
                    for attr in ["data-url", "data-link", "data-id", "data-solicitation"]:
                        attr_value = element.get(attr)
                        if attr_value:
                            if "sam.gov" in attr_value:
                                return attr_value if attr_value.startswith("http") else f"https://sam.gov{attr_value}"
                            elif len(attr_value) > 5:  # Likely a solicitation number
                                return f"https://sam.gov/opp/{attr_value}"

            # If element is just text, try to extract solicitation number
            else:
                text_content = str(element)
                solicitation_match = self._extract_solicitation_number_from_text(text_content)
                if solicitation_match:
                    return f"https://sam.gov/opp/{solicitation_match}"

        except Exception as e:
            logger.warning(f"Error extracting SAM.gov URL from element: {e}")

        # Fallback to base SAM.gov URL
        return "https://sam.gov"

    def _extract_solicitation_number_from_text(self, text: str) -> str:
        """Extract solicitation number from text using regex patterns"""
        import re

        # Common patterns for SAM.gov solicitation numbers
        patterns = [
            r"[A-Z0-9]{2,}-[A-Z0-9]{2,}-[A-Z0-9]{2,}",  # Pattern like ABC-123-DEF
            r"[A-Z]{2,}[0-9]{3,}[A-Z0-9]*",  # Pattern like ABC123456
            r"Solicitation\s*(?:Number|ID|#):\s*([A-Z0-9\-]{5,})",  # Explicit solicitation labels
            r"RFP\s*(?:Number|#):\s*([A-Z0-9\-]{5,})",  # RFP numbers
            r"IFB\s*(?:Number|#):\s*([A-Z0-9\-]{5,})",  # IFB numbers
            r"([A-Z0-9\-]{10,})",  # Any alphanumeric string of 10+ chars
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Return the first capture group if it exists, otherwise the whole match
                return match.group(1) if match.groups() else match.group(0)

        return None
