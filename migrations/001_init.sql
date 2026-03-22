-- =============================================================================
-- POSTGRESQL-ONLY MIGRATION — NOT COMPATIBLE WITH SQLITE
-- This file uses PostgreSQL-specific types: JSONB, UUID, TEXT[], TIMESTAMP,
-- CREATE OR REPLACE VIEW, and ->> / -> JSON operators.
-- The Python application (report_storage.py) manages its own SQLite schema via
-- _create_tables() and does NOT use these SQL migration files at runtime.
-- These files are only applied by docker-entrypoint-initdb.d when using
-- the optional PostgreSQL Docker service defined in docker-compose.yml.
-- =============================================================================

-- Initial schema for AccessLens

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY,
    url TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    score FLOAT NOT NULL,
    summary JSONB NOT NULL,
    metadata JSONB NOT NULL,
    request JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS issues (
    id UUID PRIMARY KEY,
    report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    issue_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT NOT NULL,
    confidence_score FLOAT NOT NULL,
    source TEXT NOT NULL,
    wcag_criteria JSONB,
    location JSONB,
    remediation JSONB,
    evidence JSONB,
    engine_name TEXT NOT NULL,
    tags TEXT[]
);

CREATE TABLE IF NOT EXISTS accessibility_trees (
    report_id UUID PRIMARY KEY REFERENCES reports(id) ON DELETE CASCADE,
    tree_data JSONB NOT NULL
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_reports_url ON reports(url);
CREATE INDEX IF NOT EXISTS idx_reports_timestamp ON reports(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_issues_report_id ON issues(report_id);
CREATE INDEX IF NOT EXISTS idx_issues_severity ON issues(severity);
CREATE INDEX IF NOT EXISTS idx_issues_type ON issues(issue_type);

-- Summary view for listings
CREATE OR REPLACE VIEW report_summaries AS
SELECT 
    r.id,
    r.url,
    r.timestamp,
    r.score,
    (r.summary->>'total_issues')::int as total_issues,
    (r.summary->'by_severity'->>'critical')::int as critical_count,
    (r.summary->'by_severity'->>'serious')::int as serious_count,
    (r.summary->'by_severity'->>'moderate')::int as moderate_count,
    (r.summary->'by_severity'->>'minor')::int as minor_count,
    r.summary->>'confidence_avg' as avg_confidence
FROM reports r;
