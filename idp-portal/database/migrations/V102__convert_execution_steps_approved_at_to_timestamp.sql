-- ---------------------------------------------------------------------------
-- V102: Convert EXECUTION_STEPS.APPROVED_AT to plain TIMESTAMP (UTC convention)
-- Convention: all timestamps in UTC, plain TIMESTAMP (V048).
-- EXECUTIONS.APPROVED_AT already plain TIMESTAMP (V101).
-- Oracle ORA-01439: use add/copy/drop/rename pattern for type change.
-- ---------------------------------------------------------------------------
ALTER SESSION SET TIME_ZONE = 'UTC';

ALTER TABLE EXECUTION_STEPS ADD (APPROVED_AT_NEW TIMESTAMP);
UPDATE EXECUTION_STEPS SET APPROVED_AT_NEW = APPROVED_AT;
ALTER TABLE EXECUTION_STEPS DROP COLUMN APPROVED_AT;
ALTER TABLE EXECUTION_STEPS RENAME COLUMN APPROVED_AT_NEW TO APPROVED_AT;

COMMENT ON COLUMN EXECUTION_STEPS.APPROVED_AT IS 'Date/heure de l''approbation du step (ADR-007). UTC timestamp (plain TIMESTAMP).';
