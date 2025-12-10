-- Add event_id column to documents table to link documents to their triggering events
-- Migration: add_event_id_to_documents.sql
-- Date: 2025-12-10

ALTER TABLE documents
ADD COLUMN event_id INTEGER;

ALTER TABLE documents
ADD CONSTRAINT documents_event_id_fkey
FOREIGN KEY (event_id)
REFERENCES case_events(id)
ON DELETE SET NULL;

-- Create index for better query performance
CREATE INDEX idx_documents_event_id ON documents(event_id);

-- Add comment
COMMENT ON COLUMN documents.event_id IS 'Links document to the case_event that triggered it (e.g., Report of Sale -> sale document)';
