-- V008: Document new EXECUTION_STEPS JSON format (Story 2.7 - Refactorisation connecteurs generiques)
-- No schema change: EXECUTION_STEPS remains CLOB. New format uses connector_type + connector_config
-- instead of is_servicenow_change. Backend _parse_execution_steps accepts legacy is_servicenow_change
-- and converts on read; _execution_steps_to_json writes only the new format.

-- Update column comment to document new JSON structure (Story 2.7, AC4)
COMMENT ON COLUMN ACTIONS_CATALOG.EXECUTION_STEPS IS 'JSON array of execution steps. New format (Story 2.7): [{"order":1,"name":"Verification","type":"prerequisite","connector_type":"none","connector_config":null,"conditional_environments":null},{"order":2,"name":"Ouverture changement","type":"execution","connector_type":"servicenow","connector_config":{},"conditional_environments":["PROD"]}]. connector_type: aap, servicenow, azuredevops, jira, github_actions, terraform, none. Legacy format with is_servicenow_change is still accepted on read and converted.';

-- Record migration (idempotent)
MERGE INTO SCHEMA_VERSION D
USING (SELECT 'V008' AS V FROM DUAL) S ON (D.VERSION = S.V)
WHEN NOT MATCHED THEN INSERT (VERSION) VALUES (S.V);
