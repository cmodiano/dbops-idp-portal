-- Story 57.17: Add SOURCE_EXECUTION_ID to SCHEDULED_EXECUTIONS
-- Links a ScheduledExecution to the source Execution that triggered its creation
-- via a schedule_execution workflow step.
-- Idempotent pour compatibilité avec baseline mis à jour (V106/V107 inclus dans baseline_flyway)
DECLARE
  v_cnt NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_cnt FROM user_tab_columns
  WHERE table_name = 'SCHEDULED_EXECUTIONS' AND column_name = 'SOURCE_EXECUTION_ID';
  IF v_cnt = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE SCHEDULED_EXECUTIONS ADD SOURCE_EXECUTION_ID NUMBER(19) DEFAULT NULL';
    EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.SOURCE_EXECUTION_ID IS ''FK logique vers EXECUTIONS(ID) — ID de l''''exécution source ayant créé cette planification via un step schedule_execution (Story 57.17). NULL si créée manuellement.''';
  END IF;
END;
/
