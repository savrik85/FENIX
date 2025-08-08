from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://fenix:fenix_password@localhost:5432/fenix"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Environment
    environment: str = "development"
    debug: bool = True

    # API Keys - AI Services
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    crawl4ai_api_key: str | None = None

    # Google Sheets Integration
    google_credentials_file: str | None = None
    google_sheet_id: str | None = None

    # Asana Integration
    asana_access_token: str | None = None
    asana_project_id: str | None = None

    # SAM.gov API
    sam_gov_api_key: str | None = None

    # Shovels AI API
    shovels_ai_api_key: str | None = None

    # Dodge Construction API
    dodge_api_key: str | None = None

    # Security
    secret_key: str = "your_secret_key_here_minimum_32_characters"
    jwt_secret_key: str = "your_jwt_secret_key_here"

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/fenix.log"

    # File Upload
    upload_path: str = "./uploads"
    max_file_size: str = "10MB"

    # Rate Limiting
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10

    # Scraping Configuration
    default_scraping_interval: int = 3600  # seconds
    max_concurrent_scraping_jobs: int = 5
    scraping_timeout: int = 300  # seconds

    # Browser Configuration (Playwright)
    browser_headless: bool = True
    browser_timeout: int = 30000  # milliseconds

    # Email Configuration
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    email_username: str | None = None
    email_password: str | None = None
    default_notification_email: str | None = None

    # Monitoring Configuration
    monitoring_enabled: bool = True
    daily_scan_hour: int = 8
    daily_scan_minute: int = 0
    min_relevance_score: float = 0.3

    # Service Discovery
    eagle_service_url: str = "http://eagle:8001"

    # Data Retention Configuration
    tender_retention_days: int = 90
    job_retention_days: int = 30
    notification_retention_days: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
