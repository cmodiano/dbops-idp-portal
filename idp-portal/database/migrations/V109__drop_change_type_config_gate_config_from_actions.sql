-- Story 57.18 Task 2: Drop deprecated columns from ACTIONS_CATALOG
-- Prerequisite: V108 migrated change_type_config data to execution_steps
ALTER TABLE ACTIONS_CATALOG DROP COLUMN CHANGE_TYPE_CONFIG;
ALTER TABLE ACTIONS_CATALOG DROP COLUMN GATE_CONFIG;
