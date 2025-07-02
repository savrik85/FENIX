import json
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
                await self.crawler.astart()
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
            await self.crawler.aclose()
        if self.session:
            await self.session.close()

    async def scrape_sam_gov(
        self, keywords: list[str], max_results: int = 100
    ) -> list[TenderData]:
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
                    logger.info(
                        "Trying Crawl4AI as fallback for enhanced data extraction"
                    )
                    return await self._scrape_with_crawl4ai(api_url, keywords)
                else:
                    logger.error("Crawl4AI not available and API failed")
                    raise Exception("Both direct API and Crawl4AI failed") from e

        except Exception as e:
            logger.error(f"All SAM.gov scraping methods failed: {e}")
            # Return empty list instead of mock data
            return []

    def _build_sam_gov_url(self, keywords: list[str], max_results: int) -> str:
        """Build SAM.gov search URL with keywords"""
        base_url = "https://sam.gov/api/prod/opportunities/v2/search"

        # Combine keywords into search query
        query = " OR ".join([f'"{keyword}"' for keyword in keywords])

        params = {
            "api_key": settings.sam_gov_api_key or "DEMO_KEY",
            "q": query,
            "size": min(max_results, 100),  # SAM.gov API limit
            "postedFrom": (datetime.now() - timedelta(days=30)).strftime("%m/%d/%Y"),
            "postedTo": datetime.now().strftime("%m/%d/%Y"),
            "ptype": "o",  # Opportunities only
        }

        return f"{base_url}?{urlencode(params)}"

    async def _scrape_sam_gov_api_direct(
        self, url: str, keywords: list[str]
    ) -> list[TenderData]:
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

    async def _scrape_with_crawl4ai(
        self, url: str, keywords: list[str]
    ) -> list[TenderData]:
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
            result = await self.crawler.arun(
                url=url,
                extraction_strategy=extraction_strategy,
                bypass_cache=True,
                js_code="window.scrollTo(0, document.body.scrollHeight);",
                wait_for="body",
            )

            if result.extracted_content:
                extracted_data = json.loads(result.extracted_content)
                return self._convert_to_tender_data(
                    extracted_data.get("opportunities", []), keywords
                )
            else:
                logger.warning("No content extracted with Crawl4AI")
                return []

        except Exception as e:
            logger.error(f"Crawl4AI extraction failed: {e}")
            return []

    def _parse_sam_gov_api_response(
        self, data: dict, keywords: list[str]
    ) -> list[TenderData]:
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
                title = item.get(
                    "title", item.get("solicitation_title", "Unknown Title")
                )
                description = item.get(
                    "description", item.get("solicitation_description", "")
                )

                # Parse dates
                posted_date = self._parse_date(
                    item.get("postedDate", item.get("posted_date"))
                )
                response_deadline = self._parse_date(
                    item.get("responseDeadLine", item.get("response_deadline"))
                )

                # Build opportunity URL
                solicitation_number = item.get(
                    "solicitationNumber", item.get("solicitation_number", "")
                )
                opportunity_url = (
                    f"https://sam.gov/opp/{solicitation_number}"
                    if solicitation_number
                    else "https://sam.gov"
                )

                # Calculate relevance score
                relevance_score = self._calculate_relevance(
                    title, description, keywords
                )

                tender = TenderData(
                    id=str(uuid.uuid4()),
                    title=title,
                    description=description[:1000],  # Limit description length
                    source=TenderSource.SAM_GOV,
                    source_url=opportunity_url,
                    posting_date=posted_date,
                    response_deadline=response_deadline,
                    estimated_value=self._parse_value(
                        item.get("estimatedValue", item.get("estimated_value"))
                    ),
                    location=self._extract_location(
                        item.get("placeOfPerformance", item.get("location", ""))
                    ),
                    naics_codes=self._extract_naics_codes(item),
                    keywords_found=self._find_keywords_in_text(
                        title + " " + description, keywords
                    ),
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
                logger.info(
                    f"Found {len(items)} opportunities with selector: {selector}"
                )
                break

        if not items:
            # Fallback: look for any element containing opportunity-like text
            items = soup.find_all(
                text=lambda text: text
                and any(keyword.lower() in text.lower() for keyword in keywords)
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

                # Create basic tender data
                tender = TenderData(
                    id=str(uuid.uuid4()),
                    title=text[:100] + "..." if len(text) > 100 else text,
                    description=text[:500] + "..." if len(text) > 500 else text,
                    source=TenderSource.SAM_GOV,
                    source_url="https://sam.gov",
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
            clean_value = (
                str(value_str).replace("$", "").replace(",", "").replace(" ", "")
            )
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

    def _calculate_relevance(
        self, title: str, description: str, keywords: list[str]
    ) -> float:
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
