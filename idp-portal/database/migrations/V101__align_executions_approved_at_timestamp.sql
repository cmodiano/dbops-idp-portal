-- ---------------------------------------------------------------------------
-- V101: Align EXECUTIONS.APPROVED_AT to plain TIMESTAMP (UTC convention)
-- Convention: all timestamps in UTC, plain TIMESTAMP (V048, V084).
-- EXECUTION_STEPS.APPROVED_AT (V099) uses TIMESTAMP WITH TIME ZONE; consider
-- aligning later if needed. Oracle ORA-01439: use add/copy/drop/rename pattern.
-- ---------------------------------------------------------------------------
ALTER TABLE EXECUTIONS ADD (APPROVED_AT_NEW TIMESTAMP);
UPDATE EXECUTIONS SET APPROVED_AT_NEW = APPROVED_AT;
ALTER TABLE EXECUTIONS DROP COLUMN APPROVED_AT;
ALTER TABLE EXECUTIONS RENAME COLUMN APPROVED_AT_NEW TO APPROVED_AT;
