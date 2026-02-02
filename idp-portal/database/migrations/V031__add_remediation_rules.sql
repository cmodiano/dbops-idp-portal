-- V031: Add REMEDIATION_RULES column to ACTIONS_CATALOG (Story 9.1)
-- AC4: Configuration des règles de remédiation par DBOPS
-- FR36: Autoremediation - détection échec et proposition actions correctives

-- Add new CLOB column for remediation rules (JSON array)
ALTER TABLE ACTIONS_CATALOG ADD (
    REMEDIATION_RULES CLOB
);

-- Check constraint for JSON format (Oracle 19+ native JSON validation)
-- Note: No constraint added; validation done in application layer for flexibility

-- Column comment documenting the JSON schema
COMMENT ON COLUMN ACTIONS_CATALOG.REMEDIATION_RULES IS 'JSON array of remediation rule objects. Schema: [{"error_pattern": "regex", "target_action_id": int, "environments": ["dev","staging","prod"], "auto_trigger": bool, "risk_level": "low|medium|high"}]. NULL means no auto-remediation configured (Story 9.1, FR36).';

-- Index for actions with remediation rules (used by get_actions_with_remediation_rules query)
-- Oracle: Use function-based index to efficiently filter non-NULL CLOB
CREATE INDEX IDX_ACTIONS_CATALOG_REMEDIATION ON ACTIONS_CATALOG(
    CASE WHEN REMEDIATION_RULES IS NOT NULL THEN ID END
);
