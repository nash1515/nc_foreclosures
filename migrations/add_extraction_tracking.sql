-- Add extraction tracking to documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS extraction_attempted_at TIMESTAMP;

-- Index for finding documents needing extraction
CREATE INDEX IF NOT EXISTS idx_documents_extraction_pending
ON documents(case_id)
WHERE ocr_text IS NOT NULL AND extraction_attempted_at IS NULL;
