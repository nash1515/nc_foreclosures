-- database/migrations/create_enrichment_review_log.sql
-- Create table for logging ambiguous enrichment results requiring manual review

CREATE TABLE IF NOT EXISTS enrichment_review_log (
    id SERIAL PRIMARY KEY,
    case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
    enrichment_type VARCHAR(50) NOT NULL,
    search_method VARCHAR(20) NOT NULL,
    search_value TEXT NOT NULL,
    matches_found INTEGER NOT NULL,
    raw_results JSONB,
    resolution_notes TEXT,
    resolved_at TIMESTAMP,
    resolved_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_review_case_id ON enrichment_review_log(case_id);
CREATE INDEX IF NOT EXISTS idx_enrichment_review_unresolved ON enrichment_review_log(resolved_at)
    WHERE resolved_at IS NULL;
