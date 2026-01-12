-- Add interest_status column to cases table
-- Values: NULL (not reviewed), 'interested', 'not_interested'
ALTER TABLE cases ADD COLUMN interest_status VARCHAR(20);

-- Add index for filtering by interest status
CREATE INDEX idx_cases_interest_status ON cases(interest_status);
