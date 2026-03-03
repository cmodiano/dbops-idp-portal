-- Story 57.17: Add SOURCE_EXECUTION_ID to SCHEDULED_EXECUTIONS
-- Links a ScheduledExecution to the source Execution that triggered its creation
-- via a schedule_execution workflow step.
ALTER TABLE SCHEDULED_EXECUTIONS
    ADD SOURCE_EXECUTION_ID NUMBER(19) DEFAULT NULL;

COMMENT ON COLUMN SCHEDULED_EXECUTIONS.SOURCE_EXECUTION_ID IS 'FK logique vers EXECUTIONS(ID) — ID de l''exécution source ayant créé cette planification via un step schedule_execution (Story 57.17). NULL si créée manuellement.';
