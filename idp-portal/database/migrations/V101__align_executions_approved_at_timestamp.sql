-- ---------------------------------------------------------------------------
-- V101: Align EXECUTIONS.APPROVED_AT to TIMESTAMP WITH TIME ZONE
-- EXECUTION_STEPS.APPROVED_AT is already TIMESTAMP WITH TIME ZONE (V099).
-- Canonical type for approval timestamps: TIMESTAMP WITH TIME ZONE.
-- Oracle ORA-01439: use add/copy/drop/rename pattern for type change.
-- ---------------------------------------------------------------------------
ALTER TABLE EXECUTIONS ADD (APPROVED_AT_NEW TIMESTAMP WITH TIME ZONE);
UPDATE EXECUTIONS SET APPROVED_AT_NEW = APPROVED_AT;
ALTER TABLE EXECUTIONS DROP COLUMN APPROVED_AT;
ALTER TABLE EXECUTIONS RENAME COLUMN APPROVED_AT_NEW TO APPROVED_AT;
