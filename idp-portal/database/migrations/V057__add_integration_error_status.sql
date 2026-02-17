-- V057: Add INTEGRATION_ERROR status and ERROR_MESSAGE column to EXECUTIONS
-- Story 18.6: Display integration error status when platform returns error
-- Date: 2026-02-07

-- 1. Add ERROR_MESSAGE column for storing integration error details
ALTER TABLE EXECUTIONS ADD (
    ERROR_MESSAGE CLOB
);

COMMENT ON COLUMN EXECUTIONS.ERROR_MESSAGE IS 'Integration error message when submission to platform fails (Story 18.6). NULL when status is not INTEGRATION_ERROR.';

-- 2. Drop existing CHECK constraint (created in V023, modified in V030)
ALTER TABLE EXECUTIONS DROP CONSTRAINT CHK_EXECUTION_STATUS;

-- 3. Recreate CHECK constraint with INTEGRATION_ERROR
ALTER TABLE EXECUTIONS ADD CONSTRAINT CHK_EXECUTION_STATUS
    CHECK (STATUS IN ('SUBMITTED', 'INTEGRATION_ERROR', 'PENDING_APPROVAL', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'));

-- 4. Update status column comment
COMMENT ON COLUMN EXECUTIONS.STATUS IS 'Execution status: SUBMITTED (submitted to platform), INTEGRATION_ERROR (failed to submit), PENDING_APPROVAL (waiting approval), RUNNING (in progress), COMPLETED (success), FAILED (failed during execution), CANCELLED (user cancelled), REJECTED (approval rejected)';
