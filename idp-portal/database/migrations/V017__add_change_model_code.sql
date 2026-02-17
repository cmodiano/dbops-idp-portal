-- V017: Add change_model_code column to ACTIONS_CATALOG (Story 2.21)
-- Pre-approved change model code for ServiceNow integration (e.g. "1516B")

ALTER TABLE ACTIONS_CATALOG ADD CHANGE_MODEL_CODE VARCHAR2(50) NULL;

COMMENT ON COLUMN ACTIONS_CATALOG.CHANGE_MODEL_CODE IS 'Pre-approved ServiceNow change model code (alphanumeric, e.g. 1516B)';
