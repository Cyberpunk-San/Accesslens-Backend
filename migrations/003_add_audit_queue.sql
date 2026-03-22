-- POSTGRESQL-ONLY MIGRATION — not used by SQLite runtime (see migrations/001_init.sql for details)

-- Async Queue state management

CREATE TABLE IF NOT EXISTS audit_queue (
    queue_id UUID PRIMARY KEY,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    engines_requested JSONB,
    report_id UUID REFERENCES reports(id) ON DELETE SET NULL,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_queue_status ON audit_queue(status, priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_audit_queue_url ON audit_queue(url);
