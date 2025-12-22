-- Add Chatham County RE enrichment columns
-- Run: PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f migrations/add_chatham_re_columns.sql

ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS chatham_re_parcel_id VARCHAR(20);
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS chatham_re_url TEXT;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS chatham_re_enriched_at TIMESTAMP;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS chatham_re_error TEXT;

-- Add index for faster lookups
CREATE INDEX IF NOT EXISTS idx_enrichments_chatham_re_parcel_id ON enrichments(chatham_re_parcel_id) WHERE chatham_re_parcel_id IS NOT NULL;
