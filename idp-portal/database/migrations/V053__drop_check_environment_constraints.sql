-- V053: Drop CHECK constraints on ENVIRONMENT columns (Story 13.7)
-- Environment values are now validated against inventory via application logic
-- This allows adding new environments without database migrations

-- Drop CHECK constraint on EXECUTIONS.ENVIRONMENT
ALTER TABLE EXECUTIONS DROP CONSTRAINT CHK_EXECUTION_ENV;

-- Drop CHECK constraint on SCHEDULED_EXECUTIONS.ENVIRONMENT
ALTER TABLE SCHEDULED_EXECUTIONS DROP CONSTRAINT CHK_SCHEDULED_ENV;

-- Comments
COMMENT ON COLUMN EXECUTIONS.ENVIRONMENT IS 'Target environment (must exist in inventory). Validated by application logic against GET /api/v1/inventory/environments.';
COMMENT ON COLUMN SCHEDULED_EXECUTIONS.ENVIRONMENT IS 'Target environment (must exist in inventory). Validated by application logic against GET /api/v1/inventory/environments.';
