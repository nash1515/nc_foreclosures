-- Add Lee County RE enrichment columns
-- Run with: PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f migrations/add_lee_re_columns.sql

ALTER TABLE enrichments
ADD COLUMN IF NOT EXISTS lee_re_account_id VARCHAR(30),
ADD COLUMN IF NOT EXISTS lee_re_url TEXT,
ADD COLUMN IF NOT EXISTS lee_re_enriched_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS lee_re_error TEXT;

-- Index for lookups
CREATE INDEX IF NOT EXISTS idx_enrichments_lee_re_account_id ON enrichments(lee_re_account_id);
