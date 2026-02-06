-- V045: Add 'integration' and 'profile' to ENTITY_TYPE constraint
-- Required for IntegrationService and ProfileService audit entries
-- (INTEGRATION_CREATED/UPDATED/DELETED, PROFILE_CREATED/UPDATED/DELETED)

ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE;

ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE CHECK (
    ENTITY_TYPE IN ('action', 'user', 'permission', 'execution', 'scheduled_execution', 'integration', 'profile')
);
