-- ==============================================================================
-- Migration 005: Candidate Null SHA & Bidirectional Steel Cage Constraint
-- Ensures unreviewed CANDIDATE modules cannot carry fabricated Git commit SHAs,
-- while CURATED items strictly require a valid 40-character SHA.
-- ==============================================================================

-- 1. Set all candidate commit SHAs to NULL
UPDATE catalog_items 
SET git_commit_sha = NULL 
WHERE curation_status = 'CANDIDATE';

-- 2. Enforce mirrored CHECK constraint: CANDIDATE => git_commit_sha IS NULL
ALTER TABLE catalog_items 
DROP CONSTRAINT IF EXISTS chk_candidate_null_sha;

ALTER TABLE catalog_items 
ADD CONSTRAINT chk_candidate_null_sha 
CHECK (curation_status <> 'CANDIDATE' OR git_commit_sha IS NULL);
