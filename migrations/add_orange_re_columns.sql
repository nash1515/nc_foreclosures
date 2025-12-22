-- Add Orange County Real Estate enrichment columns
-- Orange County uses Spatialest portal with 10-digit Parcel IDs

ALTER TABLE enrichments
ADD COLUMN IF NOT EXISTS orange_re_parcel_id VARCHAR(20),
ADD COLUMN IF NOT EXISTS orange_re_url TEXT,
ADD COLUMN IF NOT EXISTS orange_re_enriched_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS orange_re_error TEXT;

-- Index for parcel ID lookups
CREATE INDEX IF NOT EXISTS idx_enrichments_orange_re_parcel_id
ON enrichments(orange_re_parcel_id);
