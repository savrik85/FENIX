from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

from ..config import settings


Base = declarative_base()


class StoredTender(Base):
    """Stored tender data in the database"""

    __tablename__ = "stored_tenders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tender_id = Column(String(255), unique=True, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    source = Column(String(50), nullable=False, index=True)
    source_url = Column(Text)
    posting_date = Column(DateTime, index=True)
    response_deadline = Column(DateTime)
    estimated_value = Column(Float)
    location = Column(String(500))
    naics_codes = Column(JSONB, default=list)
    keywords_found = Column(JSONB, default=list)
    relevance_score = Column(Float, index=True)
    contact_info = Column(JSONB, default=dict)
    requirements = Column(JSONB, default=list)
    extracted_data = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    is_notified = Column(Boolean, default=False, index=True)


class MonitoringConfig(Base):
    """Monitoring configuration for automated scanning"""

    __tablename__ = "monitoring_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    keywords = Column(JSONB, default=list)
    sources = Column(JSONB, default=list)
    filters = Column(JSONB, default=dict)
    email_recipients = Column(JSONB, default=list)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class ScrapingJobRecord(Base):
    """Record of scraping jobs for tracking and analytics"""

    __tablename__ = "scraping_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_id = Column(String(255), unique=True, index=True)
    source = Column(String(50), nullable=False)
    keywords = Column(JSONB, default=list)
    filters = Column(JSONB, default=dict)
    status = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    results_count = Column(Float, default=0)
    error_message = Column(Text)
    job_metadata = Column(JSONB, default=dict)


class NotificationLog(Base):
    """Log of sent notifications"""

    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    tender_ids = Column(JSONB, default=list)
    email_recipients = Column(JSONB, default=list)
    subject = Column(String(255))
    sent_at = Column(DateTime, default=func.now())
    success = Column(Boolean, default=True)
    error_message = Column(Text)
    notification_metadata = Column(JSONB, default=dict)


# Database engine and session
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """Drop all database tables"""
    Base.metadata.drop_all(bind=engine)
