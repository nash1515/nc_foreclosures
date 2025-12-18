-- migrations/add_case_analyses.sql
-- AI Analysis table for storing Claude analysis results

CREATE TABLE IF NOT EXISTS case_analyses (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL UNIQUE REFERENCES cases(id) ON DELETE CASCADE,

    -- Analysis outputs
    summary TEXT,
    financials JSONB,
    red_flags JSONB,
    defendant_name VARCHAR(255),
    deed_book VARCHAR(50),
    deed_page VARCHAR(50),

    -- Discrepancy tracking
    discrepancies JSONB,

    -- Document contribution tracking
    document_contributions JSONB,

    -- Metadata
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    model_used VARCHAR(50),
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_cents INTEGER,
    requested_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_case_analyses_status ON case_analyses(status);
CREATE INDEX IF NOT EXISTS idx_case_analyses_case_id ON case_analyses(case_id);

COMMENT ON TABLE case_analyses IS 'AI analysis results for upset_bid cases';
COMMENT ON COLUMN case_analyses.financials IS 'JSON: {mortgage_amount, lender, liens[], taxes, judgments, gaps[]}';
COMMENT ON COLUMN case_analyses.red_flags IS 'JSON array: [{category, description, severity}]';
COMMENT ON COLUMN case_analyses.discrepancies IS 'JSON array: [{field, db_value, ai_value, status, resolved_at, resolved_by}]';
COMMENT ON COLUMN case_analyses.document_contributions IS 'JSON array: [{document_id, document_name, contributed_to[], key_extractions[]}]';
