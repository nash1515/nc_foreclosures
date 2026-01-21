-- Add Harnett County RE enrichment columns
-- Run: PGPASSWORD=nc_password psql -U nc_user -d nc_foreclosures -h localhost -f migrations/add_harnett_re_columns.sql

ALTER TABLE enrichments
ADD COLUMN IF NOT EXISTS harnett_re_prid VARCHAR(20),
ADD COLUMN IF NOT EXISTS harnett_re_url TEXT,
ADD COLUMN IF NOT EXISTS harnett_re_enriched_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS harnett_re_error TEXT;

-- Verify columns added
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'enrichments'
AND column_name LIKE 'harnett%'
ORDER BY column_name;
