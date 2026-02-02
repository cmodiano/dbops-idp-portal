-- V035: Add auto-remediation audit action types (Story 9.3)
-- AC5: Audit trail for auto-remediation triggers, successes, and failures
--
-- REMEDIATION_RULES schema in ACTIONS_CATALOG (already CLOB JSON from Story 9.1):
-- [
--   {
--     "error_pattern": "regex",
--     "target_action_id": integer,
--     "environments": ["dev", "staging", "prod"],
--     "auto_trigger": boolean (default: false),
--     "risk_level": "low" | "medium" | "high" (default: "medium")
--   }
-- ]
--
-- Auto-trigger constraints (enforced in application layer):
-- - Only allowed when risk_level = "low"
-- - Production environment always requires human approval (auto_trigger blocked)
-- - Audit trail captures: AUTO_REMEDIATION_TRIGGERED, AUTO_REMEDIATION_SUCCESS, AUTO_REMEDIATION_FAILED

-- Drop existing constraint to add auto-remediation types
ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE;

-- Recreate ACTION_TYPE constraint with auto-remediation types
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
        'AUTO_REMEDIATION_TRIGGERED', 'AUTO_REMEDIATION_SUCCESS', 'AUTO_REMEDIATION_FAILED'
    )
);

-- Update column comment for REMEDIATION_RULES with auto-remediation fields (Story 9.3)
COMMENT ON COLUMN ACTIONS_CATALOG.REMEDIATION_RULES IS
'JSON rules for auto-remediation: [{ error_pattern (regex), target_action_id, environments: [dev, staging, prod], auto_trigger: bool (default false), risk_level: low|medium|high (default medium) }]. Auto-trigger only allowed for risk_level=low. Production auto-trigger blocked (requires human approval).';
