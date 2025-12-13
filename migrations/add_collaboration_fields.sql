-- Add collaboration fields to cases table
ALTER TABLE cases ADD COLUMN IF NOT EXISTS our_initial_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS our_second_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS our_max_bid DECIMAL(12,2);
ALTER TABLE cases ADD COLUMN IF NOT EXISTS team_notes TEXT;

-- Add index for cases with team notes
CREATE INDEX IF NOT EXISTS idx_cases_team_notes
ON cases(id)
WHERE team_notes IS NOT NULL;
