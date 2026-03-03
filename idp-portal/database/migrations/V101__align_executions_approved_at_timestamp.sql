-- ---------------------------------------------------------------------------
-- V101: Align EXECUTIONS.APPROVED_AT to plain TIMESTAMP (UTC convention)
-- Convention: all timestamps in UTC, plain TIMESTAMP (V048, V084).
-- EXECUTION_STEPS.APPROVED_AT aligned in V102. ORA-01439: add/copy/drop/rename.
-- ---------------------------------------------------------------------------
ALTER TABLE EXECUTIONS ADD (APPROVED_AT_NEW TIMESTAMP);
UPDATE EXECUTIONS SET APPROVED_AT_NEW = APPROVED_AT;
ALTER TABLE EXECUTIONS DROP COLUMN APPROVED_AT;
ALTER TABLE EXECUTIONS RENAME COLUMN APPROVED_AT_NEW TO APPROVED_AT;
