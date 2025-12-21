-- database/migrations/create_enrichments_table.sql
-- Create enrichments table for storing external property data URLs

CREATE TABLE IF NOT EXISTS enrichments (
    id SERIAL PRIMARY KEY,
    case_id INTEGER UNIQUE REFERENCES cases(id) ON DELETE CASCADE,

    -- Wake County RE enrichment
    wake_re_account VARCHAR(20),
    wake_re_url TEXT,
    wake_re_enriched_at TIMESTAMP,
    wake_re_error TEXT,

    -- Future enrichments (placeholders)
    propwire_url TEXT,
    propwire_enriched_at TIMESTAMP,
    propwire_error TEXT,

    deed_url TEXT,
    deed_enriched_at TIMESTAMP,
    deed_error TEXT,

    property_info_url TEXT,
    property_info_enriched_at TIMESTAMP,
    property_info_error TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichments_case_id ON enrichments(case_id);
CREATE INDEX IF NOT EXISTS idx_enrichments_wake_re_pending ON enrichments(case_id)
    WHERE wake_re_url IS NULL AND wake_re_error IS NULL;
