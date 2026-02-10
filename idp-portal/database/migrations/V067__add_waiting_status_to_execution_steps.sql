-- Story 25.2: Add WAITING status to EXECUTION_STEPS
-- Adds WAITING to the CHECK constraint on STATUS column
-- Constraint name is CHK_STEP_STATUS (defined in V025__create_execution_steps.sql).
--
-- Rollback (if needed):
-- ALTER TABLE EXECUTION_STEPS DROP CONSTRAINT CHK_STEP_STATUS;
-- ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT CHK_STEP_STATUS
-- CHECK (STATUS IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED'));
-- COMMENT ON COLUMN EXECUTION_STEPS.STATUS IS
-- 'Step status: PENDING (queued), RUNNING (in progress), COMPLETED (success), FAILED (error), SKIPPED (skipped due to condition)';

-- Drop existing CHECK constraint on STATUS (name from V025)
ALTER TABLE EXECUTION_STEPS DROP CONSTRAINT CHK_STEP_STATUS;

-- Add new CHECK constraint with WAITING status
ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT CHK_STEP_STATUS
CHECK (STATUS IN ('PENDING', 'WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED'));

-- Update comment on STATUS column
COMMENT ON COLUMN EXECUTION_STEPS.STATUS IS
'Step status: PENDING (queued), WAITING (gate conditions not met), RUNNING (in progress), COMPLETED (success), FAILED (error), SKIPPED (skipped due to condition)';
