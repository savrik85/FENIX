import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from ..config import settings
from ..models.tender_models import TenderData, TenderSource


class ACCClient:
    """Autodesk Construction Cloud API Client"""

    def __init__(self):
        self.base_url = "https://developer.api.autodesk.com"
        self.auth_url = "https://developer.api.autodesk.com/authentication/v2/token"
        self.client_id = settings.autodesk_client_id
        self.client_secret = settings.autodesk_client_secret
        self.account_id = settings.autodesk_account_id
        self.email = settings.autodesk_email
        self.password = settings.autodesk_password
        self.access_token = None
        self.token_expires_at = None

        # Debug credentials
        logger.info(f"ACC Client initialized - client_id: {self.client_id[:10] if self.client_id else 'None'}...")
        logger.info(f"ACC Client initialized - account_id: {self.account_id[:10] if self.account_id else 'None'}...")

    async def authenticate(self) -> bool:
        """Authenticate with Autodesk API using existing OAuth token or 2-legged fallback"""
        try:
            # Try to get OAuth token from main app
            from ..main import oauth_tokens

            if "autodesk" in oauth_tokens:
                token_info = oauth_tokens["autodesk"]
                self.access_token = token_info.get("access_token")
                expires_in = token_info.get("expires_in", 3600)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.info("Using OAuth token from 3-legged authentication")
                return True

            # Fallback to 2-legged OAuth
            async with httpx.AsyncClient() as client:
                auth_data = {
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "data:read account:read user-profile:read",
                }

                headers = {"Content-Type": "application/x-www-form-urlencoded"}

                response = await client.post(self.auth_url, data=auth_data, headers=headers)

                if response.status_code == 200:
                    token_data = response.json()
                    self.access_token = token_data.get("access_token")
                    expires_in = token_data.get("expires_in", 3600)
                    self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    logger.info("Successfully authenticated with Autodesk API using 2-legged OAuth")
                    return True
                else:
                    logger.error(f"Authentication failed: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return False

    async def is_token_valid(self) -> bool:
        """Check if current access token is still valid"""
        if not self.access_token or not self.token_expires_at:
            return False
        return datetime.now() < self.token_expires_at - timedelta(minutes=5)  # 5 min buffer

    async def ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token"""
        if not await self.is_token_valid():
            return await self.authenticate()
        return True

    async def get_projects(self) -> list[dict[str, Any]]:
        """Get all ACC projects for the account"""
        if not await self.ensure_authenticated():
            raise Exception("Failed to authenticate")

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }

                # Get projects from ACC using Project API
                url = f"{self.base_url}/project/v1/hubs"

                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    hubs = data.get("data", [])
                    logger.info(f"Retrieved {len(hubs)} hubs from Autodesk")
                    logger.info(f"Hubs data sample: {hubs[:1] if hubs else 'No hubs'}")

                    # For each hub, get projects
                    all_projects = []
                    for hub in hubs:
                        hub_id = hub.get("id")
                        hub_name = hub.get("attributes", {}).get("name", "Unknown Hub")
                        logger.info(f"Processing hub: {hub_name} ({hub_id})")

                        if hub_id:
                            projects_url = f"{self.base_url}/project/v1/hubs/{hub_id}/projects"
                            logger.info(f"Fetching projects from: {projects_url}")
                            projects_response = await client.get(projects_url, headers=headers, timeout=30.0)

                            if projects_response.status_code == 200:
                                projects_data = projects_response.json()
                                projects = projects_data.get("data", [])
                                all_projects.extend(projects)
                                logger.info(f"Retrieved {len(projects)} projects from hub {hub_id}")
                                if projects:
                                    logger.info(f"Sample project: {projects[0] if projects else 'None'}")
                            else:
                                logger.warning(
                                    f"Failed to get projects from hub {hub_id}: "
                                    f"{projects_response.status_code} - {projects_response.text}"
                                )

                    logger.info(f"Total projects collected: {len(all_projects)}")
                    return all_projects
                else:
                    logger.error(f"Failed to get hubs: {response.status_code} - {response.text}")
                    return []

        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            return []

    async def get_project_issues(self, project_id: str) -> list[dict[str, Any]]:
        """Get issues for a specific project"""
        if not await self.ensure_authenticated():
            raise Exception("Failed to authenticate")

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }

                url = f"{self.base_url}/construction/issues/v1/containers/{project_id}/quality-issues"

                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    issues = data.get("results", [])
                    logger.info(f"Retrieved {len(issues)} issues for project {project_id}")
                    return issues
                else:
                    logger.warning(f"Failed to get issues for project {project_id}: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Error getting issues for project {project_id}: {e}")
            return []

    async def get_project_rfis(self, project_id: str) -> list[dict[str, Any]]:
        """Get RFIs (Request for Information) for a specific project"""
        if not await self.ensure_authenticated():
            raise Exception("Failed to authenticate")

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }

                url = f"{self.base_url}/construction/rfis/v1/containers/{project_id}/rfis"

                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    rfis = data.get("results", [])
                    logger.info(f"Retrieved {len(rfis)} RFIs for project {project_id}")
                    return rfis
                else:
                    logger.warning(f"Failed to get RFIs for project {project_id}: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Error getting RFIs for project {project_id}: {e}")
            return []

    async def search_project_files(self, project_id: str, keywords: list[str]) -> list[dict[str, Any]]:
        """Search for files in a project containing specific keywords"""
        if not await self.ensure_authenticated():
            raise Exception("Failed to authenticate")

        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }

                # Get project files
                url = f"{self.base_url}/data/v1/projects/{project_id}/folders"

                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    data = response.json()
                    folders = data.get("data", [])

                    # Search through folders for relevant files
                    relevant_files = []
                    for folder in folders:
                        folder_name = folder.get("attributes", {}).get("displayName", "").lower()

                        # Check if folder name contains keywords
                        if any(keyword.lower() in folder_name for keyword in keywords):
                            relevant_files.append(folder)

                    logger.info(f"Found {len(relevant_files)} relevant files for project {project_id}")
                    return relevant_files
                else:
                    logger.warning(f"Failed to get files for project {project_id}: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"Error searching files for project {project_id}: {e}")
            return []


class ACCScraper:
    """Autodesk Construction Cloud data scraper for FENIX"""

    def __init__(self):
        self.client = ACCClient()
        self.is_initialized = False

    async def initialize(self):
        """Initialize the ACC scraper"""
        logger.info("Initializing ACC Scraper")
        self.is_initialized = True

    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up ACC Scraper")
        self.is_initialized = False

    async def scrape_acc_data(self, keywords: list[str], max_results: int = 100) -> list[TenderData]:
        """
        Scrape ACC for construction project data relevant to fenestration
        """
        logger.info(f"Starting ACC scraping with keywords: {keywords}")

        if not self.client.client_id or not self.client.client_secret:
            logger.error("ACC credentials not configured")
            logger.error(f"client_id: {self.client.client_id[:10] if self.client.client_id else 'None'}...")
            logger.error(f"client_secret: {self.client.client_secret[:10] if self.client.client_secret else 'None'}...")
            return []

        try:
            # Get all projects
            logger.info("Calling get_projects()...")
            projects = await self.client.get_projects()
            logger.info(f"get_projects() returned {len(projects)} projects")

            if not projects:
                logger.warning(
                    "No projects found in ACC account - this may be normal if account has no active projects"
                )
                return []

            all_results = []

            for project in projects[:10]:  # Limit to first 10 projects for testing
                project_id = project.get("id")
                project_name = project.get("name", "Unknown Project")

                logger.info(f"Processing project: {project_name} ({project_id})")

                # Get project issues
                issues = await self.client.get_project_issues(project_id)

                # Get project RFIs
                rfis = await self.client.get_project_rfis(project_id)

                # Search project files
                files = await self.client.search_project_files(project_id, keywords)

                # Process issues into TenderData
                for issue in issues:
                    if self._is_relevant_to_keywords(issue, keywords):
                        tender = self._convert_issue_to_tender(issue, project)
                        if tender:
                            all_results.append(tender)

                # Process RFIs into TenderData
                for rfi in rfis:
                    if self._is_relevant_to_keywords(rfi, keywords):
                        tender = self._convert_rfi_to_tender(rfi, project)
                        if tender:
                            all_results.append(tender)

                # Process files into TenderData (potential opportunities)
                for file_item in files:
                    if self._is_relevant_to_keywords(file_item, keywords):
                        tender = self._convert_file_to_tender(file_item, project)
                        if tender:
                            all_results.append(tender)

                # Rate limiting
                await asyncio.sleep(1)

                if len(all_results) >= max_results:
                    break

            logger.info(f"ACC scraping completed, found {len(all_results)} results")
            return all_results[:max_results]

        except Exception as e:
            logger.error(f"Error in ACC scraping: {e}")
            return []

    def _is_relevant_to_keywords(self, item: dict[str, Any], keywords: list[str]) -> bool:
        """Check if an item is relevant to the search keywords"""
        item_text = ""

        # Extract text from various fields
        if isinstance(item, dict):
            item_text += str(item.get("title", "")) + " "
            item_text += str(item.get("displayName", "")) + " "
            item_text += str(item.get("description", "")) + " "
            item_text += str(item.get("subject", "")) + " "

            # Check attributes
            attributes = item.get("attributes", {})
            if isinstance(attributes, dict):
                item_text += str(attributes.get("displayName", "")) + " "
                item_text += str(attributes.get("name", "")) + " "

        item_text = item_text.lower()

        # Check if any keyword matches
        return any(keyword.lower() in item_text for keyword in keywords)

    def _convert_issue_to_tender(self, issue: dict[str, Any], project: dict[str, Any]) -> TenderData | None:
        """Convert ACC issue to TenderData format"""
        try:
            issue_id = issue.get("id", str(uuid.uuid4()))
            title = issue.get("title") or f"Issue in {project.get('name', 'Unknown Project')}"
            description = issue.get("description", "")

            # Extract keywords found
            keywords_found = []
            issue_text = f"{title} {description}".lower()
            fenestration_terms = ["window", "door", "glazing", "fenestration", "curtain wall", "storefront"]
            for term in fenestration_terms:
                if term in issue_text:
                    keywords_found.append(term)

            return TenderData(
                tender_id=issue_id,
                title=f"ACC Issue: {title}",
                description=description,
                source=TenderSource.AUTODESK_ACC,
                source_url=f"https://acc.autodesk.com/projects/{project.get('id')}/issues/{issue_id}",
                posting_date=datetime.now(),
                response_deadline=None,
                estimated_value=None,
                location=project.get("businessUnitId", ""),
                keywords_found=keywords_found,
                relevance_score=0.7,
                contact_info={
                    "project_name": project.get("name"),
                    "project_id": project.get("id"),
                },
                extracted_data={
                    "type": "issue",
                    "project": project,
                    "issue_data": issue,
                },
            )

        except Exception as e:
            logger.error(f"Error converting issue to tender: {e}")
            return None

    def _convert_rfi_to_tender(self, rfi: dict[str, Any], project: dict[str, Any]) -> TenderData | None:
        """Convert ACC RFI to TenderData format"""
        try:
            rfi_id = rfi.get("id", str(uuid.uuid4()))
            title = rfi.get("subject") or f"RFI in {project.get('name', 'Unknown Project')}"
            description = rfi.get("question", "")

            # Extract keywords found
            keywords_found = []
            rfi_text = f"{title} {description}".lower()
            fenestration_terms = ["window", "door", "glazing", "fenestration", "curtain wall", "storefront"]
            for term in fenestration_terms:
                if term in rfi_text:
                    keywords_found.append(term)

            return TenderData(
                tender_id=rfi_id,
                title=f"ACC RFI: {title}",
                description=description,
                source=TenderSource.AUTODESK_ACC,
                source_url=f"https://acc.autodesk.com/projects/{project.get('id')}/rfis/{rfi_id}",
                posting_date=datetime.now(),
                response_deadline=None,
                estimated_value=None,
                location=project.get("businessUnitId", ""),
                keywords_found=keywords_found,
                relevance_score=0.8,
                contact_info={
                    "project_name": project.get("name"),
                    "project_id": project.get("id"),
                },
                extracted_data={
                    "type": "rfi",
                    "project": project,
                    "rfi_data": rfi,
                },
            )

        except Exception as e:
            logger.error(f"Error converting RFI to tender: {e}")
            return None

    def _convert_file_to_tender(self, file_item: dict[str, Any], project: dict[str, Any]) -> TenderData | None:
        """Convert ACC file/folder to TenderData format"""
        try:
            file_id = file_item.get("id", str(uuid.uuid4()))
            attributes = file_item.get("attributes", {})
            title = attributes.get("displayName") or f"File in {project.get('name', 'Unknown Project')}"

            # Extract keywords found
            keywords_found = []
            file_text = title.lower()
            fenestration_terms = ["window", "door", "glazing", "fenestration", "curtain wall", "storefront"]
            for term in fenestration_terms:
                if term in file_text:
                    keywords_found.append(term)

            return TenderData(
                tender_id=file_id,
                title=f"ACC Document: {title}",
                description=f"Construction document from project {project.get('name')}",
                source=TenderSource.AUTODESK_ACC,
                source_url=f"https://acc.autodesk.com/projects/{project.get('id')}/files/{file_id}",
                posting_date=datetime.now(),
                response_deadline=None,
                estimated_value=None,
                location=project.get("businessUnitId", ""),
                keywords_found=keywords_found,
                relevance_score=0.6,
                contact_info={
                    "project_name": project.get("name"),
                    "project_id": project.get("id"),
                },
                extracted_data={
                    "type": "file",
                    "project": project,
                    "file_data": file_item,
                },
            )

        except Exception as e:
            logger.error(f"Error converting file to tender: {e}")
            return None
