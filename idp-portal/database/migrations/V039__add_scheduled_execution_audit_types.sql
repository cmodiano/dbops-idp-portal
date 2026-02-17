-- V039: Add scheduled execution audit types (Story 11.3)
-- AC6: Audit trail for scheduled execution creation
--
-- Adds:
-- - ACTION_TYPE: SCHEDULED_EXECUTION_CREATED
-- - ENTITY_TYPE: scheduled_execution

-- Drop existing constraints to add scheduled execution types
ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE;
ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE;

-- Recreate ACTION_TYPE constraint with scheduled execution types
ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE CHECK (
    ACTION_TYPE IN (
        -- Action lifecycle (V004)
        'ACTION_CREATED', 'ACTION_UPDATED', 'ACTION_PUBLISHED', 'ACTION_DISABLED', 'ACTION_ENABLED',
        -- Execution lifecycle (V028)
        'EXECUTION_SUBMITTED', 'EXECUTION_STARTED', 'EXECUTION_COMPLETED', 'EXECUTION_FAILED',
        -- ServiceNow change (V028)
        'SERVICENOW_CHANGE_CREATED',
        -- Approval workflow (V032 - Story 7.4)
        'EXECUTION_PENDING_APPROVAL', 'EXECUTION_APPROVED', 'EXECUTION_REJECTED',
        -- Remediation (V034 - Story 9.2)
        'REMEDIATION_EXECUTION_CREATED',
        -- Auto-remediation (V035 - Story 9.3, AC5)
        'AUTO_REMEDIATION_TRIGGERED', 'AUTO_REMEDIATION_SUCCESS', 'AUTO_REMEDIATION_FAILED',
        -- Scheduled execution (V039 - Story 11.3, AC6)
        'SCHEDULED_EXECUTION_CREATED'
    )
);

-- Recreate ENTITY_TYPE constraint with scheduled_execution type
ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE CHECK (
    ENTITY_TYPE IN ('action', 'user', 'permission', 'execution', 'scheduled_execution')
);
