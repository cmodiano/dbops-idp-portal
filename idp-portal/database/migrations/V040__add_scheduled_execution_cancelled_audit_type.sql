-- V040: Add SCHEDULED_EXECUTION_CANCELLED audit type (Story 11.6)
-- AC5: Audit trail for scheduled execution cancellation

-- Drop existing constraint to add new action type
ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE;

-- Recreate ACTION_TYPE constraint with scheduled execution cancellation type
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
        -- Scheduled execution (V039, V040 - Story 11.3, Story 11.6)
        'SCHEDULED_EXECUTION_CREATED', 'SCHEDULED_EXECUTION_CANCELLED'
    )
);
