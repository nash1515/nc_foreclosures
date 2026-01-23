-- Add Zillow enrichment columns to enrichments table
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_url TEXT;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_zestimate INTEGER;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_enriched_at TIMESTAMP;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS zillow_error TEXT;
