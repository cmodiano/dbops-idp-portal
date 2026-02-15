-- V074: Add BUSINESS_RULE_POLICIES column to ACTIONS_CATALOG (Story 28.1)
-- AC1: JSON schema for business rule policies evaluated on step output (review_if_modified, etc.)

-- Add CLOB column for business rule policies (JSON)
ALTER TABLE ACTIONS_CATALOG ADD (
    BUSINESS_RULE_POLICIES CLOB
);

COMMENT ON COLUMN ACTIONS_CATALOG.BUSINESS_RULE_POLICIES IS 'JSON schema defining business rule policies evaluated on step output. Structure: on_step_output[] with when (step_type, output_key), policy (type, require_review_if_modified, auto_approve_if_none_match). NULL means no policies configured (Story 28.1, FR27/FR28).';
