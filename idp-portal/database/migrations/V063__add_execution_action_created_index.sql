-- V063: Add composite index on EXECUTIONS(ACTION_ID, CREATED_AT)
-- Django executions/0003 - Optimizes queries filtering by action + ordering by date

CREATE INDEX IDX_EXEC_ACTION_CREATED ON EXECUTIONS(ACTION_ID, CREATED_AT);
