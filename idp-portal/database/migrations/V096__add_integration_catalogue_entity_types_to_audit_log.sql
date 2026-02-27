-- V096: Add integration_type_catalogue, integration_action, feature_flag, business_rule_policy to ENTITY_TYPE constraint
-- V086 Phase 5 recreated CK_AUDIT_LOG_ENTITY_TYPE with V045 values only, dropping V065 additions.
-- This restores the entity types required for IntegrationTypeCatalogue and IntegrationAction audit signals.

ALTER TABLE AUDIT_LOG DROP CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE;

ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE CHECK (
    ENTITY_TYPE IN (
        'action', 'user', 'permission', 'execution',
        'scheduled_execution', 'integration', 'profile',
        'feature_flag', 'integration_type_catalogue', 'integration_action', 'business_rule_policy'
    )
);
