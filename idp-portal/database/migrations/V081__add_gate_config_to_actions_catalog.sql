-- Story 31.6: Add gate_config JSON field to ACTIONS_CATALOG
-- Stores per-gate integration selection (e.g., which ServiceNow integration to use)
ALTER TABLE ACTIONS_CATALOG ADD (GATE_CONFIG CLOB CHECK (GATE_CONFIG IS JSON));

COMMENT ON COLUMN ACTIONS_CATALOG.GATE_CONFIG IS
'JSON configuration des gates : integration par type de gate (ex: servicenow_change.integration_id). Story 31.6.';
