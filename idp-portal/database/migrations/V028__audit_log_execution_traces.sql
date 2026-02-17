-- V028: Extend AUDIT_LOG for execution traces (Story 6.1)
-- FR30, FR35: Immutable audit trail for every execution
-- NFR8: Append-only - no UPDATE, no DELETE.
-- Enforced at application level (audit_repository exposes only create_entry + list/get).
-- Optional: add trigger or policy to reject UPDATE/DELETE for defense in depth (Task 5.1).

-- Add CORRELATION_ID column for log correlation
ALTER TABLE AUDIT_LOG ADD (
    CORRELATION_ID VARCHAR2(64)
);

-- Index for correlation_id queries
CREATE INDEX IDX_AUDIT_LOG_CORRELATION ON AUDIT_LOG(CORRELATION_ID);

-- Drop existing constraints to recreate with extended values
ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE;
ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE;

-- Recreate ACTION_TYPE constraint with execution types
ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE CHECK (
    ACTION_TYPE IN (
        -- Action lifecycle (existing)
        'ACTION_CREATED', 'ACTION_UPDATED', 'ACTION_PUBLISHED', 'ACTION_DISABLED', 'ACTION_ENABLED',
        -- Execution lifecycle (new - Story 6.1)
        'EXECUTION_SUBMITTED', 'EXECUTION_STARTED', 'EXECUTION_COMPLETED', 'EXECUTION_FAILED',
        -- ServiceNow change (new - Story 6.1, AC2)
        'SERVICENOW_CHANGE_CREATED'
    )
);

-- Recreate ENTITY_TYPE constraint with execution type
ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE CHECK (
    ENTITY_TYPE IN ('action', 'user', 'permission', 'execution')
);

-- Column comment for CORRELATION_ID
COMMENT ON COLUMN AUDIT_LOG.CORRELATION_ID IS 'Request correlation ID linking audit entry to technical logs (Story 6.1, AC6)';
