-- Add Durham County RE enrichment columns
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS durham_re_parcelpk VARCHAR(20);
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS durham_re_url TEXT;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS durham_re_enriched_at TIMESTAMP;
ALTER TABLE enrichments ADD COLUMN IF NOT EXISTS durham_re_error TEXT;
