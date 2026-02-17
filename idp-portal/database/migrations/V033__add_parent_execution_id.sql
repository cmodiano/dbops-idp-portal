-- V033__add_parent_execution_id.sql
-- Story 9.2: Add parent_execution_id column to EXECUTIONS for remediation linking

-- Add nullable column for parent execution reference
ALTER TABLE EXECUTIONS
ADD PARENT_EXECUTION_ID NUMBER(19);

-- Add foreign key constraint to ensure parent exists
ALTER TABLE EXECUTIONS
ADD CONSTRAINT FK_EXECUTIONS_PARENT
FOREIGN KEY (PARENT_EXECUTION_ID)
REFERENCES EXECUTIONS(ID);

-- Add index for efficient child lookup queries
CREATE INDEX IDX_EXECUTIONS_PARENT_ID
ON EXECUTIONS(PARENT_EXECUTION_ID);

-- Add column comment for documentation
COMMENT ON COLUMN EXECUTIONS.PARENT_EXECUTION_ID IS
    'ID of parent execution if this is a remediation action';
