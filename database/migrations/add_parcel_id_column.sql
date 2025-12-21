-- database/migrations/add_parcel_id_column.sql
-- Add parcel_id column to cases table for Wake County RE enrichment

ALTER TABLE cases ADD COLUMN IF NOT EXISTS parcel_id VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_cases_parcel_id ON cases(parcel_id);

COMMENT ON COLUMN cases.parcel_id IS 'County parcel/PIN number (10-digit for Wake County)';
