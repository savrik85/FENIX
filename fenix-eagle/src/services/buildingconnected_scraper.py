from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from ..config import settings
from ..models.tender_models import TenderData, TenderSource


class BuildingConnectedClient:
    """BuildingConnected API Client for tender/bid data"""

    def __init__(self):
        self.base_url = "https://developer.api.autodesk.com"
        self.bc_base_url = "https://developer.api.autodesk.com/construction/buildingconnected"
        self.auth_url = "https://developer.api.autodesk.com/authentication/v2/token"
        self.client_id = settings.autodesk_client_id
        self.client_secret = settings.autodesk_client_secret
        self.access_token = None
        self.token_expires_at = None

        logger.info(
            f"BuildingConnected Client initialized - client_id: {self.client_id[:10] if self.client_id else 'None'}..."
        )

    async def authenticate(self) -> bool:
        """Authenticate with BuildingConnected API using existing OAuth token or 2-legged fallback"""
        try:
            # First try to use existing 3-legged OAuth token from saved session
            from ..main import oauth_tokens

            if "autodesk" in oauth_tokens:
                token_info = oauth_tokens["autodesk"]
                self.access_token = token_info.get("access_token")
                if self.access_token:
                    logger.info("Using existing 3-legged OAuth token for BuildingConnected")
                    return True

            # Fallback to 2-legged OAuth for server-to-server auth
            logger.info("Using 2-legged OAuth for BuildingConnected authentication")
            async with httpx.AsyncClient() as client:
                auth_data = {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "data:read data:write",
                }

                response = await client.post(
                    self.auth_url,
                    data=auth_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    logger.info("Successfully authenticated with BuildingConnected API")
                    return True
                else:
                    logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    async def ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication token"""
        if not self.access_token or (self.token_expires_at and datetime.now() >= self.token_expires_at):
            return await self.authenticate()
        return True

    async def get_opportunities(self) -> list[dict[str, Any]]:
        """Get all opportunities (tenders/bids) from BuildingConnected"""
        if not await self.ensure_authenticated():
            raise Exception("Failed to authenticate")

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }

                # Get opportunities from BuildingConnected API
                # Try different endpoints
                urls_to_try = [
                    f"{self.bc_base_url}/v2/opportunities",
                    f"{self.bc_base_url}/v1/opportunities",
                    f"{self.bc_base_url}/bid-board/opportunities",
                    "https://api.buildingconnected.com/v2/opportunities",
                ]

                response = None
                for url in urls_to_try:
                    logger.info(f"Trying to fetch opportunities from: {url}")
                    try:
                        response = await client.get(url, headers=headers, timeout=30.0)
                        logger.info(f"Response status: {response.status_code}")

                        if response.status_code == 200:
                            logger.info(f"Success with {url}")
                            break
                        elif response.status_code == 401:
                            logger.error(f"Authentication failed for {url}")
                        elif response.status_code == 403:
                            logger.error(f"Access forbidden for {url} - may need Pro account or additional permissions")
                        else:
                            logger.warning(f"Failed with {url}: {response.status_code} - {response.text[:200]}")
                    except Exception as e:
                        logger.error(f"Error accessing {url}: {e}")

                if response and response.status_code == 200:
                    data = response.json()
                    logger.info(f"Response keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")

                    # Try different response formats
                    opportunities = []
                    if isinstance(data, list):
                        opportunities = data
                    elif isinstance(data, dict):
                        opportunities = data.get("results", data.get("data", data.get("opportunities", [])))

                    logger.info(f"Retrieved {len(opportunities)} opportunities from BuildingConnected")

                    if opportunities:
                        logger.info(f"Sample opportunity: {opportunities[0] if opportunities else 'None'}")

                    return opportunities
                else:
                    logger.error(f"All endpoints failed. Last response: {response.status_code} - {response.text}")
                    return []

        except Exception as e:
            logger.error(f"Error getting opportunities: {e}")
            return []

    async def get_opportunity_details(self, opportunity_id: str) -> dict[str, Any]:
        """Get detailed information about a specific opportunity"""
        if not await self.ensure_authenticated():
            raise Exception("Failed to authenticate")

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }

                url = f"{self.bc_base_url}/v2/opportunities/{opportunity_id}"
                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Failed to get opportunity details: {response.status_code}")
                    return {}

        except Exception as e:
            logger.error(f"Error getting opportunity details: {e}")
            return {}


class BuildingConnectedScraper:
    """Scraper for BuildingConnected tender data"""

    def __init__(self):
        self.client = BuildingConnectedClient()

    async def scrape_buildingconnected_data(self, keywords: list[str], max_results: int = 100) -> list[TenderData]:
        """
        Scrape BuildingConnected for construction tender/bid data
        """
        logger.info(f"Starting BuildingConnected scraping with keywords: {keywords}")

        if not self.client.client_id or not self.client.client_secret:
            logger.error("BuildingConnected credentials not configured")
            return []

        try:
            # Get all opportunities
            logger.info("Calling get_opportunities()...")
            opportunities = await self.client.get_opportunities()
            logger.info(f"get_opportunities() returned {len(opportunities)} opportunities")

            if not opportunities:
                logger.warning("No opportunities found in BuildingConnected account")
                return []

            all_results = []

            for opp in opportunities[:max_results]:
                opp_id = opp.get("id")
                opp_name = opp.get("name", "Unknown Opportunity")

                logger.info(f"Processing opportunity: {opp_name} ({opp_id})")

                # Check if opportunity matches keywords
                description = opp.get("description", "")
                title = opp_name
                combined_text = f"{title} {description}".lower()

                # Check if any keyword matches
                matched_keywords = [kw for kw in keywords if kw.lower() in combined_text]

                if matched_keywords or not keywords:  # Include all if no keywords specified
                    # Create tender data
                    tender = TenderData(
                        tender_id=opp_id,
                        title=title,
                        description=description or "No description available",
                        source=TenderSource.BUILDING_CONNECTED,
                        source_url=f"https://app.buildingconnected.com/opportunities/{opp_id}" if opp_id else None,
                        posting_date=datetime.fromisoformat(
                            opp.get("created_at", datetime.now().isoformat()).replace("Z", "+00:00")
                        ),
                        response_deadline=datetime.fromisoformat(
                            opp.get("bid_date", datetime.now().isoformat()).replace("Z", "+00:00")
                        )
                        if opp.get("bid_date")
                        else None,
                        estimated_value=opp.get("estimated_value"),
                        location=opp.get("location", {}).get("address", ""),
                        keywords_found=matched_keywords,
                        relevance_score=len(matched_keywords) / len(keywords) if keywords else 0.5,
                        contact_info={
                            "company": opp.get("owner", {}).get("name", ""),
                            "email": opp.get("owner", {}).get("email", ""),
                        },
                        extracted_data={
                            "opportunity_type": opp.get("type", ""),
                            "status": opp.get("status", ""),
                            "trade": opp.get("trade", ""),
                            "raw_data": opp,
                        },
                    )

                    all_results.append(tender)
                    logger.info(f"Added opportunity: {title} with {len(matched_keywords)} keyword matches")

                    if len(all_results) >= max_results:
                        break

            logger.info(f"BuildingConnected scraping completed. Found {len(all_results)} matching opportunities")
            return all_results

        except Exception as e:
            logger.error(f"Error during BuildingConnected scraping: {e}")
            return []


# Initialize scraper instance
buildingconnected_scraper = BuildingConnectedScraper()
