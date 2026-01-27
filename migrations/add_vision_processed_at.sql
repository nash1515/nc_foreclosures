-- Add vision_processed_at column to documents table
-- Tracks when a document was processed by Claude Vision for structured extraction

ALTER TABLE documents ADD COLUMN IF NOT EXISTS vision_processed_at TIMESTAMP;

COMMENT ON COLUMN documents.vision_processed_at IS 'Timestamp when document was processed by Claude Vision';

-- Index for efficient filtering of unprocessed documents
CREATE INDEX IF NOT EXISTS idx_documents_vision_processed_at ON documents(vision_processed_at);
