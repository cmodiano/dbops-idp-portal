-- V094: Add SERVICE_LOGIN to AUDIT_LOG ACTION_TYPE constraint
-- Story 49.3: Dedicated audit type for service account LDAP authentication
-- Aligns Oracle CHECK with Django AuditActionType (core/models.py).

ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE;

ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE CHECK (
    ACTION_TYPE IN (
        -- Action lifecycle
        'ACTION_CREATED', 'ACTION_UPDATED', 'ACTION_PUBLISHED',
        'ACTION_DISABLED', 'ACTION_DISABLED_INTEGRATION_DELETED', 'ACTION_ENABLED', 'ACTION_DELETED',
        'ACTION_DEACTIVATED', 'ACTION_REACTIVATED',

        -- Profile lifecycle
        'PROFILE_CREATED', 'PROFILE_UPDATED', 'PROFILE_DELETED',
        'PROFILE_UPDATE_REJECTED',

        -- Integration lifecycle
        'INTEGRATION_CREATED', 'INTEGRATION_UPDATED', 'INTEGRATION_DELETED',

        -- Integration type catalogue
        'INTEGRATION_TYPE_CREATED', 'INTEGRATION_TYPE_UPDATED',
        'INTEGRATION_ACTION_CREATED', 'INTEGRATION_ACTION_UPDATED',

        -- Integration status / migration (Story 24.3, 24.4)
        'INTEGRATION_STATUS_UPDATED', 'INTEGRATION_MARKED_LEGACY',

        -- Execution lifecycle
        'EXECUTION_SUBMITTED', 'EXECUTION_STARTED', 'EXECUTION_RUNNING',
        'EXECUTION_COMPLETED', 'EXECUTION_FAILED', 'EXECUTION_CANCELLED',
        'EXECUTION_PENDING_APPROVAL', 'EXECUTION_APPROVED', 'EXECUTION_REJECTED',
        'EXECUTION_TARGET_FORBIDDEN', 'EXECUTION_INTEGRATION_ERROR',

        -- Execution guard-rails invalid/deprecated integration (Story 24.4)
        'EXECUTION_BLOCKED_INVALID_INTEGRATION', 'EXECUTION_DEPRECATED_INTEGRATION_WARNING',
        'WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION',

        -- ServiceNow change
        'SERVICENOW_CHANGE_CREATED',

        -- Remediation / auto-remediation
        'REMEDIATION_EXECUTION_CREATED',
        'AUTO_REMEDIATION_TRIGGERED', 'AUTO_REMEDIATION_SUCCESS', 'AUTO_REMEDIATION_FAILED',

        -- Scheduled executions
        'SCHEDULED_EXECUTION_CREATED', 'SCHEDULED_EXECUTION_RECURRING_CREATED',
        'SCHEDULED_EXECUTION_EXECUTED', 'SCHEDULED_EXECUTION_CANCELLED',
        'SCHEDULED_EXECUTION_RECURRING_DISABLED',

        -- User / Auth / Favorites
        'USER_CREATED', 'USER_UPDATED', 'USER_LOGIN', 'USER_LOGOUT', 'USER_REFRESH',
        'API_KEY_TOKEN_EXCHANGE',  -- present in Django model since Story 31.x, never added to Oracle -- pragma: allowlist secret
        'FAVORITE_ADDED', 'FAVORITE_REMOVED',
        'SERVICE_LOGIN',  -- Story 49.3: service account LDAP login

        -- Execution step retry
        'EXECUTION_STEP_RETRY_ATTEMPT', 'EXECUTION_STEP_RETRY_SUCCESS',
        'EXECUTION_STEP_RETRY_EXHAUSTED', 'EXECUTION_STEP_RETRY_ABORTED',

        -- Condition gates (Story 25.2, 25.3)
        'EXECUTION_STEP_WAITING',
        'EXECUTION_STEP_GATE_SATISFIED',
        'EXECUTION_STEP_GATE_TIMEOUT',

        -- Feature flags
        'FEATURE_FLAG_CREATED', 'FEATURE_FLAG_UPDATED'
    )
);

COMMENT ON COLUMN AUDIT_LOG.ACTION_TYPE IS 'V094: SERVICE_LOGIN added for service account LDAP authentication audit trail. API_KEY_TOKEN_EXCHANGE backfilled (was in Django model but missing from Oracle constraint since Story 31.x).';
