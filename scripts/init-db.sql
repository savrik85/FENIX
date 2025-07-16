-- FENIX Database Initialization Script
-- This script is run automatically when PostgreSQL container starts

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create stored_tenders table
CREATE TABLE IF NOT EXISTS stored_tenders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tender_id VARCHAR(255) UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    source VARCHAR(50) NOT NULL,
    source_url TEXT,
    posting_date TIMESTAMP,
    response_deadline TIMESTAMP,
    estimated_value DECIMAL,
    location VARCHAR(500),
    naics_codes JSONB DEFAULT '[]',
    keywords_found JSONB DEFAULT '[]',
    relevance_score DECIMAL CHECK (relevance_score >= 0 AND relevance_score <= 1),
    contact_info JSONB DEFAULT '{}',
    requirements JSONB DEFAULT '[]',
    extracted_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_notified BOOLEAN DEFAULT FALSE
);

-- Create monitoring_configs table
CREATE TABLE IF NOT EXISTS monitoring_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    keywords JSONB DEFAULT '[]',
    sources JSONB DEFAULT '[]',
    filters JSONB DEFAULT '{}',
    email_recipients JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create scraping_jobs table
CREATE TABLE IF NOT EXISTS scraping_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id VARCHAR(255) UNIQUE,
    source VARCHAR(50) NOT NULL,
    keywords JSONB DEFAULT '[]',
    filters JSONB DEFAULT '{}',
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    results_count INTEGER DEFAULT 0,
    error_message TEXT,
    job_metadata JSONB DEFAULT '{}'
);

-- Create notification_logs table
CREATE TABLE IF NOT EXISTS notification_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tender_ids JSONB DEFAULT '[]',
    email_recipients JSONB DEFAULT '[]',
    subject VARCHAR(255),
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    notification_metadata JSONB DEFAULT '{}'
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_stored_tenders_source ON stored_tenders(source);
CREATE INDEX IF NOT EXISTS idx_stored_tenders_posting_date ON stored_tenders(posting_date);
CREATE INDEX IF NOT EXISTS idx_stored_tenders_relevance_score ON stored_tenders(relevance_score);
CREATE INDEX IF NOT EXISTS idx_stored_tenders_is_notified ON stored_tenders(is_notified);
CREATE INDEX IF NOT EXISTS idx_stored_tenders_source_posting_date ON stored_tenders(source, posting_date);
CREATE INDEX IF NOT EXISTS idx_stored_tenders_relevance_posting ON stored_tenders(relevance_score, posting_date);

-- GIN indexes for JSONB columns (require JSONB type)
CREATE INDEX IF NOT EXISTS idx_stored_tenders_keywords ON stored_tenders USING gin(keywords_found jsonb_ops);
CREATE INDEX IF NOT EXISTS idx_stored_tenders_naics ON stored_tenders USING gin(naics_codes jsonb_ops);

-- Monitoring configs indexes
CREATE INDEX IF NOT EXISTS idx_monitoring_configs_active ON monitoring_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_monitoring_configs_name ON monitoring_configs(name);

-- Scraping jobs indexes
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status ON scraping_jobs(status);
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_status_created ON scraping_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_scraping_jobs_source ON scraping_jobs(source);

-- Notification logs indexes
CREATE INDEX IF NOT EXISTS idx_notification_logs_sent_at ON notification_logs(sent_at);
CREATE INDEX IF NOT EXISTS idx_notification_logs_success ON notification_logs(success);

-- Insert default monitoring configuration
INSERT INTO monitoring_configs (name, keywords, sources, email_recipients, is_active)
VALUES (
    'default_windows_doors',
    '["windows", "doors", "glazing", "fenestration", "curtain wall", "storefront", "facade", "window installation", "door installation"]',
    '["sam.gov", "construction.com", "dodge", "nyc.opendata", "shovels.ai"]',
    '["savrikk@gmail.com"]',
    true
) ON CONFLICT DO NOTHING;

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for automatic updated_at updates
CREATE TRIGGER update_stored_tenders_updated_at
    BEFORE UPDATE ON stored_tenders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_monitoring_configs_updated_at
    BEFORE UPDATE ON monitoring_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fenix;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fenix;
