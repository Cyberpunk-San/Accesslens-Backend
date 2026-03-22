-- POSTGRESQL-ONLY MIGRATION — not used by SQLite runtime (see migrations/001_init.sql for details)

-- Performance Indices for Reports and Issues

CREATE INDEX IF NOT EXISTS idx_reports_score ON reports(score);
CREATE INDEX IF NOT EXISTS idx_reports_summary_critical ON reports ((CAST(summary->'by_severity'->>'critical' AS integer)));

CREATE INDEX IF NOT EXISTS idx_issues_confidence ON issues(confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_issues_engine ON issues(engine_name);

-- Composite Index for quick issue lookup by report and severity
CREATE INDEX IF NOT EXISTS idx_issues_report_severity ON issues(report_id, severity);
