import logging
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import func

from ..config import settings
from ..database.models import StoredTender, get_db


logger = logging.getLogger(__name__)


class DeduplicationService:
    """Service for detecting and managing duplicate tenders"""

    def __init__(self):
        self.similarity_threshold = getattr(settings, "deduplication_similarity_threshold", 0.8)
        self.max_stored_tenders = getattr(settings, "max_stored_tenders", 10000)

    async def detect_new_tenders(self, scraped_tenders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect which tenders are truly new (not duplicates)

        Args:
            scraped_tenders: List of scraped tender data

        Returns:
            List of new (non-duplicate) tenders
        """
        db = next(get_db())
        new_tenders = []

        try:
            logger.info(f"Checking {len(scraped_tenders)} tenders for duplicates")

            for tender in scraped_tenders:
                # Check if tender already exists
                if not await self._is_duplicate(tender, db):
                    new_tenders.append(tender)
                else:
                    logger.debug(f"Duplicate found: {tender.get('title', 'Unknown')}")

            logger.info(f"Found {len(new_tenders)} new tenders out of {len(scraped_tenders)}")

            return new_tenders

        except Exception as e:
            logger.error(f"Error detecting duplicates: {str(e)}")
            # In case of error, return all tenders to avoid losing data
            return scraped_tenders
        finally:
            db.close()

    async def _is_duplicate(self, tender: dict[str, Any], db) -> bool:
        """
        Check if a tender is a duplicate of an existing one

        Args:
            tender: Tender data to check
            db: Database session

        Returns:
            True if duplicate, False if new
        """
        try:
            # Method 1: Exact match by source_url
            if tender.get("source_url"):
                existing_by_url = db.query(StoredTender).filter(StoredTender.source_url == tender["source_url"]).first()

                if existing_by_url:
                    logger.debug(f"Duplicate found by URL: {tender['source_url']}")
                    return True

            # Method 2: Exact match by tender_id (if available)
            if tender.get("tender_id"):
                existing_by_id = db.query(StoredTender).filter(StoredTender.tender_id == tender["tender_id"]).first()

                if existing_by_id:
                    logger.debug(f"Duplicate found by ID: {tender['tender_id']}")
                    return True

            # Method 3: Similarity-based matching
            if await self._is_similar_tender(tender, db):
                return True

            return False

        except Exception as e:
            logger.error(f"Error checking for duplicates: {str(e)}")
            return False

    async def _is_similar_tender(self, tender: dict[str, Any], db) -> bool:
        """
        Check if tender is similar to existing ones using text similarity

        Args:
            tender: Tender data to check
            db: Database session

        Returns:
            True if similar tender exists, False otherwise
        """
        try:
            # Get potentially similar tenders from same source
            source = tender.get("source", "")
            title = tender.get("title", "")

            if not title:
                return False

            # Query tenders from same source with similar posting dates
            similar_candidates = (
                db.query(StoredTender)
                .filter(
                    StoredTender.source == source,
                    StoredTender.title.ilike(f"%{title.split()[0]}%"),  # Basic keyword match
                )
                .limit(50)
                .all()
            )  # Limit to avoid performance issues

            # Check similarity with each candidate
            for candidate in similar_candidates:
                if self._calculate_similarity(tender, candidate) > self.similarity_threshold:
                    logger.debug(f"Similar tender found: {candidate.title}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking similarity: {str(e)}")
            return False

    def _calculate_similarity(self, tender1: dict[str, Any], tender2: StoredTender) -> float:
        """
        Calculate similarity score between two tenders

        Args:
            tender1: New tender data
            tender2: Existing tender from database

        Returns:
            Similarity score between 0 and 1
        """
        try:
            scores = []

            # Title similarity (most important)
            title1 = tender1.get("title", "").lower()
            title2 = tender2.title.lower() if tender2.title else ""

            if title1 and title2:
                title_similarity = SequenceMatcher(None, title1, title2).ratio()
                scores.append(title_similarity * 0.5)  # 50% weight

            # Description similarity
            desc1 = tender1.get("description", "").lower()
            desc2 = tender2.description.lower() if tender2.description else ""

            if desc1 and desc2:
                desc_similarity = SequenceMatcher(None, desc1, desc2).ratio()
                scores.append(desc_similarity * 0.3)  # 30% weight

            # Location similarity
            loc1 = tender1.get("location", "").lower()
            loc2 = tender2.location.lower() if tender2.location else ""

            if loc1 and loc2:
                loc_similarity = SequenceMatcher(None, loc1, loc2).ratio()
                scores.append(loc_similarity * 0.2)  # 20% weight

            # Return average score
            return sum(scores) / len(scores) if scores else 0.0

        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0

    async def store_new_tenders(self, new_tenders: list[dict[str, Any]]) -> list[StoredTender]:
        """
        Store new tenders in the database

        Args:
            new_tenders: List of new tender data

        Returns:
            List of stored tender objects
        """
        db = next(get_db())
        stored_tenders = []

        try:
            logger.info(f"Storing {len(new_tenders)} new tenders")

            for tender_data in new_tenders:
                try:
                    # Create StoredTender object
                    stored_tender = StoredTender(
                        tender_id=tender_data.get("tender_id"),
                        title=tender_data.get("title", ""),
                        description=tender_data.get("description", ""),
                        source=tender_data.get("source", ""),
                        source_url=tender_data.get("source_url", ""),
                        posting_date=self._parse_datetime(tender_data.get("posting_date")),
                        response_deadline=self._parse_datetime(tender_data.get("response_deadline")),
                        estimated_value=tender_data.get("estimated_value"),
                        location=tender_data.get("location"),
                        naics_codes=tender_data.get("naics_codes", []),
                        keywords_found=tender_data.get("keywords_found", []),
                        relevance_score=tender_data.get("relevance_score"),
                        contact_info=tender_data.get("contact_info", {}),
                        requirements=tender_data.get("requirements", []),
                        extracted_data=tender_data.get("extracted_data", {}),
                        is_notified=False,
                    )

                    db.add(stored_tender)
                    stored_tenders.append(stored_tender)

                except Exception as e:
                    logger.error(f"Error storing tender: {str(e)}")
                    continue

            # Commit all changes
            db.commit()

            # Mark as notified
            for tender in stored_tenders:
                tender.is_notified = True

            db.commit()

            logger.info(f"Successfully stored {len(stored_tenders)} tenders")

            # Clean up old tenders if needed
            await self._cleanup_old_tenders(db)

            return stored_tenders

        except Exception as e:
            db.rollback()
            logger.error(f"Error storing tenders: {str(e)}")
            raise e
        finally:
            db.close()

    def _parse_datetime(self, date_value: Any) -> datetime | None:
        """Parse datetime from various formats"""
        if not date_value:
            return None

        if isinstance(date_value, datetime):
            return date_value

        if isinstance(date_value, str):
            # Try different datetime formats
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_value, fmt)
                except ValueError:
                    continue

        return None

    async def _cleanup_old_tenders(self, db):
        """Clean up old tenders if we exceed max_stored_tenders"""
        try:
            tender_count = db.query(StoredTender).count()

            if tender_count > self.max_stored_tenders:
                # Delete oldest tenders with low relevance scores
                excess_count = tender_count - self.max_stored_tenders

                old_tenders = (
                    db.query(StoredTender)
                    .filter(StoredTender.relevance_score < 0.5)
                    .order_by(StoredTender.created_at.asc())
                    .limit(excess_count)
                    .all()
                )

                for tender in old_tenders:
                    db.delete(tender)

                db.commit()
                logger.info(f"Cleaned up {len(old_tenders)} old tenders")

        except Exception as e:
            logger.error(f"Error cleaning up old tenders: {str(e)}")

    async def get_stored_tenders(
        self,
        source: str | None = None,
        min_relevance: float | None = None,
        limit: int = 100,
    ) -> list[StoredTender]:
        """
        Get stored tenders with optional filtering

        Args:
            source: Filter by source
            min_relevance: Minimum relevance score
            limit: Maximum number of results

        Returns:
            List of stored tenders
        """
        db = next(get_db())

        try:
            query = db.query(StoredTender)

            if source:
                query = query.filter(StoredTender.source == source)

            if min_relevance:
                query = query.filter(StoredTender.relevance_score >= min_relevance)

            query = query.order_by(StoredTender.created_at.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

        except Exception as e:
            logger.error(f"Error getting stored tenders: {str(e)}")
            return []
        finally:
            db.close()

    async def update_tender_notification_status(self, tender_ids: list[str], is_notified: bool = True):
        """
        Update notification status for tenders

        Args:
            tender_ids: List of tender IDs to update
            is_notified: New notification status
        """
        db = next(get_db())

        try:
            db.query(StoredTender).filter(StoredTender.tender_id.in_(tender_ids)).update(
                {"is_notified": is_notified}, synchronize_session=False
            )

            db.commit()
            logger.info(f"Updated notification status for {len(tender_ids)} tenders")

        except Exception as e:
            db.rollback()
            logger.error(f"Error updating notification status: {str(e)}")
            raise e
        finally:
            db.close()

    async def get_duplicate_statistics(self) -> dict[str, Any]:
        """
        Get statistics about duplicate detection

        Returns:
            Dict with duplicate statistics
        """
        db = next(get_db())

        try:
            # Get counts by source
            source_counts = (
                db.query(StoredTender.source, func.count(StoredTender.id).label("count"))
                .group_by(StoredTender.source)
                .all()
            )

            # Get average relevance scores
            avg_relevance = db.query(func.avg(StoredTender.relevance_score)).scalar()

            # Get notification statistics
            notified_count = db.query(StoredTender).filter(StoredTender.is_notified.is_(True)).count()

            total_count = db.query(StoredTender).count()

            return {
                "total_tenders": total_count,
                "notified_tenders": notified_count,
                "pending_notifications": total_count - notified_count,
                "average_relevance_score": float(avg_relevance) if avg_relevance else 0.0,
                "source_distribution": dict(source_counts),
                "similarity_threshold": self.similarity_threshold,
                "max_stored_tenders": self.max_stored_tenders,
            }

        except Exception as e:
            logger.error(f"Error getting duplicate statistics: {str(e)}")
            return {}
        finally:
            db.close()
