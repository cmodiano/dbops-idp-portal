-- V034: Add remediation audit action type (Story 9.2)
-- AC4: Audit trail for remediation execution creation
-- Extends V032 to include REMEDIATION_EXECUTION_CREATED

-- Drop existing constraint to add remediation type
ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE;

-- Recreate ACTION_TYPE constraint with remediation type
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
        'REMEDIATION_EXECUTION_CREATED'
    )
);
