import asyncio
import logging
from datetime import datetime, timedelta

from celery import Celery
from celery.schedules import crontab

from ..config import settings
from ..database.models import MonitoringConfig, get_db
from .deduplication_service import DeduplicationService
from .email_service import EmailService
from .http_client_service import EagleServiceClient


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "fenix_scheduler",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.services.scheduler"],
)

# Celery configuration
celery_app.conf.update(
    timezone="Europe/Prague",
    beat_schedule={
        "daily-tender-monitoring": {
            "task": "src.services.scheduler.daily_tender_scan",
            "schedule": crontab(
                hour=getattr(settings, "daily_scan_hour", 8),
                minute=getattr(settings, "daily_scan_minute", 0),
            ),
        },
        "cleanup-old-data": {
            "task": "src.services.scheduler.cleanup_old_data",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        },
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


@celery_app.task(bind=True, max_retries=3)
def daily_tender_scan(self):
    """
    Daily scan for new tenders across all configured sources
    """
    try:
        logger.info("Starting daily tender scan...")

        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_daily_tender_scan_async())

        logger.info(f"Daily tender scan completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Daily tender scan failed: {str(e)}")

        # Retry with exponential backoff
        if self.request.retries < 3:
            raise self.retry(countdown=60 * (2**self.request.retries), exc=e) from e

        # Final failure
        raise e


async def _daily_tender_scan_async():
    """
    Async implementation of daily tender scan
    """
    db = next(get_db())
    deduplication_service = DeduplicationService()
    email_service = EmailService()

    total_new_tenders = 0
    scan_results = []

    try:
        # Use HTTP client to communicate with Eagle service in separate container
        eagle_url = getattr(settings, "eagle_service_url", "http://eagle:8001")

        async with EagleServiceClient(eagle_base_url=eagle_url) as http_client:
            # Health check - ensure Eagle service is reachable
            logger.info("Performing health check on Eagle service...")
            is_healthy = await http_client.health_check()
            if not is_healthy:
                logger.error("Eagle service is not healthy, aborting scan")
                return {
                    "status": "failed",
                    "error": "Eagle service unavailable",
                    "timestamp": datetime.now().isoformat(),
                }

            # Get all active monitoring configurations
            monitoring_configs = db.query(MonitoringConfig).filter_by(is_active=True).all()

            if not monitoring_configs:
                logger.warning("No active monitoring configurations found")
                return {
                    "status": "completed",
                    "new_tenders": 0,
                    "message": "No active configs",
                }

            # Process each monitoring configuration
            for config in monitoring_configs:
                logger.info(f"Processing monitoring config: {config.name}")

                config_new_tenders = []

                # Scrape each source
                for source in config.sources:
                    try:
                        logger.info(f"Scraping source: {source}")

                        # Create scraping job via HTTP API
                        job_response = await http_client.create_scraping_job(
                            source=source,
                            keywords=config.keywords,
                            filters=config.filters or {},
                            max_results=50,
                        )

                        if not job_response or not job_response.get("job_id"):
                            logger.error(f"Failed to create job for {source}")
                            continue

                        job_id = job_response.get("job_id")
                        logger.info(f"Created scraping job {job_id} for source {source}")

                        # Wait for job completion (with timeout)
                        job_status = await http_client.wait_for_job_completion(
                            job_id=job_id,
                            timeout=600,  # Increase timeout to 10 minutes
                            poll_interval=5,  # Check every 5 seconds
                        )

                        if not job_status or job_status.get("status") != "completed":
                            logger.error(f"Job failed or timed out for {source}")
                            continue

                        # Get results
                        results = await http_client.get_job_results(job_id)

                        if results and results.get("tenders"):
                            # Filter for relevance
                            relevant_tenders = [
                                tender
                                for tender in results["tenders"]
                                if (tender.get("relevance_score") or 0) >= getattr(settings, "min_relevance_score", 0.3)
                            ]

                            config_new_tenders.extend(relevant_tenders)
                            logger.info(f"Found {len(relevant_tenders)} relevant tenders from {source}")

                    except Exception as e:
                        logger.error(f"Error scraping {source}: {str(e)}")
                        # Add this error to scan results for reporting
                        scan_results.append(
                            {
                                "config": config.name,
                                "source": source,
                                "status": "error",
                                "error": str(e),
                                "new_tenders": 0,
                            }
                        )
                        continue

                # Deduplicate tenders
                if config_new_tenders:
                    new_tenders = await deduplication_service.detect_new_tenders(config_new_tenders)

                    if new_tenders:
                        # Store new tenders
                        await deduplication_service.store_new_tenders(new_tenders)

                        # Send email notification
                        if config.email_recipients:
                            try:
                                email_result = await email_service.send_tender_notification(
                                    tenders=new_tenders,
                                    recipients=config.email_recipients,
                                    config_name=config.name,
                                )
                                if email_result.get("success"):
                                    count = len(config.email_recipients)
                                    logger.info(f"Email sent to {count} recipients")
                                else:
                                    logger.error(f"Email failed: {email_result.get('error')}")
                            except Exception as e:
                                logger.error(f"Failed to send email notification: {str(e)}")

                        total_new_tenders += len(new_tenders)
                        scan_results.append(
                            {
                                "config": config.name,
                                "new_tenders": len(new_tenders),
                                "sources_scanned": len(config.sources),
                            }
                        )

                        logger.info(f"Found {len(new_tenders)} new tenders for config {config.name}")
                    else:
                        # Check if we should send empty report for this config
                        if (
                            hasattr(config, "send_empty_reports")
                            and config.send_empty_reports
                            and config.email_recipients
                        ):
                            try:
                                empty_report_result = await email_service.send_empty_report_notification(
                                    recipients=config.email_recipients,
                                    config_name=config.name,
                                    scan_results=[
                                        {
                                            "config": config.name,
                                            "sources_scanned": len(config.sources),
                                        }
                                    ],
                                )
                                if empty_report_result.get("success"):
                                    logger.info("Empty report sent successfully")
                                else:
                                    error_msg = empty_report_result.get("error")
                                    logger.error(f"Empty report failed: {error_msg}")
                            except Exception as e:
                                logger.error(f"Failed to send empty report: {str(e)}")

                        # Add scan results even when no new tenders found
                        scan_results.append(
                            {
                                "config": config.name,
                                "new_tenders": 0,
                                "sources_scanned": len(config.sources),
                            }
                        )

            result = {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "total_new_tenders": total_new_tenders,
                "configs_processed": len(monitoring_configs),
                "scan_results": scan_results,
            }

            logger.info(f"Daily scan completed successfully: {total_new_tenders} new tenders found")
            return result

    except Exception as e:
        logger.error(f"Daily scan failed: {str(e)}")
        raise e
    finally:
        # Cleanup resources
        await http_client.cleanup()
        db.close()


# _wait_for_job_completion function removed - now handled by HTTPClientService


@celery_app.task
def cleanup_old_data():
    """
    Clean up old data from the database
    """
    try:
        logger.info("Starting database cleanup...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_cleanup_old_data_async())

        logger.info(f"Database cleanup completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Database cleanup failed: {str(e)}")
        raise e


async def _cleanup_old_data_async():
    """
    Async implementation of database cleanup
    """
    from ..database.models import NotificationLog, ScrapingJobRecord, StoredTender

    db = next(get_db())

    try:
        # Define cleanup thresholds
        tender_retention_days = getattr(settings, "tender_retention_days", 90)
        job_retention_days = getattr(settings, "job_retention_days", 30)
        notification_retention_days = getattr(settings, "notification_retention_days", 60)

        cutoff_date_tenders = datetime.now() - timedelta(days=tender_retention_days)
        cutoff_date_jobs = datetime.now() - timedelta(days=job_retention_days)
        cutoff_date_notifications = datetime.now() - timedelta(days=notification_retention_days)

        # Clean up old tenders (keep only recent and high-relevance ones)
        old_tenders = (
            db.query(StoredTender)
            .filter(
                StoredTender.created_at < cutoff_date_tenders,
                StoredTender.relevance_score < 0.7,  # Keep high-relevance tenders longer
            )
            .count()
        )

        db.query(StoredTender).filter(
            StoredTender.created_at < cutoff_date_tenders,
            StoredTender.relevance_score < 0.7,
        ).delete(synchronize_session=False)

        # Clean up old scraping jobs
        old_jobs = db.query(ScrapingJobRecord).filter(ScrapingJobRecord.created_at < cutoff_date_jobs).count()

        db.query(ScrapingJobRecord).filter(ScrapingJobRecord.created_at < cutoff_date_jobs).delete(
            synchronize_session=False
        )

        # Clean up old notification logs
        old_notifications = (
            db.query(NotificationLog).filter(NotificationLog.sent_at < cutoff_date_notifications).count()
        )

        db.query(NotificationLog).filter(NotificationLog.sent_at < cutoff_date_notifications).delete(
            synchronize_session=False
        )

        db.commit()

        result = {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "cleaned_up": {
                "tenders": old_tenders,
                "jobs": old_jobs,
                "notifications": old_notifications,
            },
        }

        logger.info(f"Cleanup completed: {result}")
        return result

    except Exception as e:
        db.rollback()
        logger.error(f"Cleanup failed: {str(e)}")
        raise e
    finally:
        db.close()


@celery_app.task
def manual_tender_scan(config_name: str = None):
    """
    Manual trigger for tender scanning
    """
    try:
        logger.info(f"Starting manual tender scan for config: {config_name}")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(_manual_scan_async(config_name))

        logger.info(f"Manual scan completed: {result}")
        return result

    except Exception as e:
        logger.error(f"Manual scan failed: {str(e)}")
        raise e


async def _manual_scan_async(config_name: str = None):
    """
    Async implementation of manual scan
    """
    # Similar to daily scan but can target specific config
    db = next(get_db())

    try:
        query = db.query(MonitoringConfig).filter_by(is_active=True)

        if config_name:
            query = query.filter_by(name=config_name)

        configs = query.all()

        if not configs:
            return {"status": "error", "message": "No matching configurations found"}

        # Run the same logic as daily scan - it handles its own HTTP client
        return await _daily_tender_scan_async()

    finally:
        db.close()


if __name__ == "__main__":
    # For testing purposes
    logger.info("Starting Celery worker...")
    celery_app.start()
