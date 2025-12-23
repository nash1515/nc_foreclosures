-- Add closed_sold_at timestamp for grace period monitoring
ALTER TABLE cases ADD COLUMN IF NOT EXISTS closed_sold_at TIMESTAMP;

-- Partial index for efficient querying of grace period cases
CREATE INDEX IF NOT EXISTS idx_cases_closed_sold_at ON cases (closed_sold_at)
WHERE classification = 'closed_sold' AND closed_sold_at IS NOT NULL;
