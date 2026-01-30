-- V003: Add EXECUTION_STEPS and CHANGE_TYPE_CONFIG columns to ACTIONS_CATALOG
-- Story 2.2 - Definir les etapes d'execution et le changement ServiceNow
-- FR2: DBOPS peut definir les etapes d'execution d'une action
-- FR4: DBOPS peut definir le type de changement associe a une action

-- Add columns only if missing (idempotent)
DECLARE
  v_cnt NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM user_tab_columns
  WHERE table_name = 'ACTIONS_CATALOG' AND column_name = 'EXECUTION_STEPS';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE ACTIONS_CATALOG ADD EXECUTION_STEPS CLOB';
  END IF;

  SELECT COUNT(*) INTO v_cnt FROM user_tab_columns
  WHERE table_name = 'ACTIONS_CATALOG' AND column_name = 'CHANGE_TYPE_CONFIG';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE ACTIONS_CATALOG ADD CHANGE_TYPE_CONFIG CLOB';
  END IF;
END;
/

-- Task 1.2: Column comments documenting JSON structure
COMMENT ON COLUMN ACTIONS_CATALOG.EXECUTION_STEPS IS 'JSON array of execution steps. Example: [{"order":1,"name":"Verification pre-requis","type":"prerequisite","is_servicenow_change":false,"conditional_environments":null},{"order":2,"name":"Ouverture changement","type":"execution","is_servicenow_change":true,"conditional_environments":["STAGING","PROD"]}]. Valid types: prerequisite, execution, verification';

COMMENT ON COLUMN ACTIONS_CATALOG.CHANGE_TYPE_CONFIG IS 'JSON object mapping environment to change type. Example: {"DEV":"pre_approved","STAGING":"pre_approved","PROD":"cab"}. Valid types: pre_approved, cab';
