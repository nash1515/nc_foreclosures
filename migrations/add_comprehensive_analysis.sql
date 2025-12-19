-- Add comprehensive_analysis JSONB column to case_analyses table
-- This stores the new 5-section analysis structure:
-- - executive_summary
-- - chronological_timeline
-- - parties_analysis
-- - legal_procedural_analysis
-- - conclusion_and_takeaways

ALTER TABLE case_analyses
ADD COLUMN IF NOT EXISTS comprehensive_analysis JSONB;

-- Add comment for documentation
COMMENT ON COLUMN case_analyses.comprehensive_analysis IS 'Structured 5-section comprehensive case analysis with timeline, parties, legal analysis, and conclusions';
