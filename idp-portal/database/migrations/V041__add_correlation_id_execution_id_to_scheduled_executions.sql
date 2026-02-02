-- V041: Add CORRELATION_ID and EXECUTION_ID to SCHEDULED_EXECUTIONS (Story 11.6)
-- HIGH-1 FIX: AC10 requires correlation_id in details modal
-- HIGH-2 FIX: AC10 requires link to effective execution when status=executed

-- Add CORRELATION_ID column for request tracing
ALTER TABLE SCHEDULED_EXECUTIONS ADD (
    CORRELATION_ID VARCHAR2(100)
);

-- Add EXECUTION_ID column to link to the effective execution when status=executed
ALTER TABLE SCHEDULED_EXECUTIONS ADD (
    EXECUTION_ID NUMBER
);

-- Add foreign key constraint to EXECUTIONS (optional, nullable for pending/cancelled)
ALTER TABLE SCHEDULED_EXECUTIONS ADD CONSTRAINT FK_SCHEDULED_EXEC_EXECUTION
    FOREIGN KEY (EXECUTION_ID) REFERENCES EXECUTIONS(ID);

-- Add index for execution_id lookups
CREATE INDEX IDX_SCHEDULED_EXEC_EXECUTION ON SCHEDULED_EXECUTIONS(EXECUTION_ID);

-- Column comments
COMMENT ON COLUMN SCHEDULED_EXECUTIONS.CORRELATION_ID IS 'Unique correlation ID for request tracing (Story 11.6, AC10)';
COMMENT ON COLUMN SCHEDULED_EXECUTIONS.EXECUTION_ID IS 'FK to EXECUTIONS - ID of the effective execution when status=executed (Story 11.6, AC10)';
