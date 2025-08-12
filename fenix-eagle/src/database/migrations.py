#!/usr/bin/env python3
"""
Database migration script for FENIX Eagle
"""

import logging
import sys
from datetime import datetime

from sqlalchemy import text

from .models import (
    MonitoringConfig,
    create_tables,
    engine,
    get_db,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_default_monitoring_config():
    """Create default monitoring configuration"""
    db = next(get_db())

    try:
        # Check if default config already exists
        existing = (
            db.query(MonitoringConfig).filter_by(name="default_windows_doors").first()
        )

        if existing:
            logger.info("Default monitoring config already exists")
            return

        # Create default config
        default_config = MonitoringConfig(
            name="default_windows_doors",
            keywords=[
                "windows",
                "doors",
                "glazing",
                "fenestration",
                "curtain wall",
                "storefront",
                "facade",
            ],
            sources=[
                "sam.gov",
                "construction.com",
                "dodge",
                "nyc.opendata",
                "shovels.ai",
            ],
            email_recipients=["savrikk@gmail.com"],  # Default email
            is_active=True,
        )

        db.add(default_config)
        db.commit()
        logger.info("Default monitoring configuration created")

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating default monitoring config: {e}")
        raise
    finally:
        db.close()


def create_indexes():
    """Create additional database indexes for performance"""
    with engine.connect() as conn:
        try:
            # Additional indexes for stored_tenders
            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_stored_tenders_source_posting_date
                ON stored_tenders(source, posting_date);
            """
                )
            )

            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_stored_tenders_relevance_posting
                ON stored_tenders(relevance_score, posting_date);
            """
                )
            )

            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_stored_tenders_keywords
                ON stored_tenders USING gin(keywords_found jsonb_ops);
            """
                )
            )

            # Index for monitoring configs
            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_monitoring_configs_active
                ON monitoring_configs(is_active);
            """
                )
            )

            # Index for scraping jobs
            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status_created
                ON scraping_jobs(status, created_at);
            """
                )
            )

            conn.commit()
            logger.info("Additional indexes created successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"Error creating indexes: {e}")
            raise


def migrate_database():
    """Run database migrations"""
    try:
        logger.info("Starting database migration...")

        # Create tables
        logger.info("Creating tables...")
        create_tables()

        # Create indexes
        logger.info("Creating indexes...")
        create_indexes()

        # Create default data
        logger.info("Creating default monitoring configuration...")
        create_default_monitoring_config()

        logger.info("Database migration completed successfully!")

    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        sys.exit(1)


def check_database_connection():
    """Check if database is accessible"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("FENIX Eagle Database Migration")
    logger.info(f"Timestamp: {datetime.now()}")

    # Check database connection
    if not check_database_connection():
        logger.error("Cannot connect to database. Migration aborted.")
        sys.exit(1)

    # Run migrations
    migrate_database()

    logger.info("Migration script completed successfully!")
