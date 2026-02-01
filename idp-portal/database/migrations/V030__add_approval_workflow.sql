-- V030: Add approval workflow columns to EXECUTIONS (Story 7.4)
-- AC1-AC6: DBA approval workflow for high-impact production executions

-- Add new columns for approval tracking
ALTER TABLE EXECUTIONS ADD (
    APPROVED_BY NUMBER(10),
    APPROVED_AT TIMESTAMP WITH TIME ZONE,
    APPROVAL_COMMENT VARCHAR2(1000)
);

-- Add foreign key constraint for APPROVED_BY
ALTER TABLE EXECUTIONS ADD CONSTRAINT FK_EXECUTIONS_APPROVED_BY
    FOREIGN KEY (APPROVED_BY) REFERENCES USERS(ID);

-- Drop and recreate the CHECK constraint to include REJECTED status
ALTER TABLE EXECUTIONS DROP CONSTRAINT CHK_EXECUTION_STATUS;
ALTER TABLE EXECUTIONS ADD CONSTRAINT CHK_EXECUTION_STATUS
    CHECK (STATUS IN ('SUBMITTED', 'PENDING_APPROVAL', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'));

-- Index for pending approvals query (DBA dashboard)
-- Oracle: Use function-based index with CASE expression
CREATE INDEX IDX_EXECUTIONS_PENDING_APPROVAL ON EXECUTIONS(
    CASE WHEN STATUS = 'PENDING_APPROVAL' THEN ID END
);

-- Comments
COMMENT ON COLUMN EXECUTIONS.APPROVED_BY IS 'FK to USERS - DBA who approved/rejected the execution (Story 7.4)';
COMMENT ON COLUMN EXECUTIONS.APPROVED_AT IS 'Timestamp of approval/rejection decision (Story 7.4)';
COMMENT ON COLUMN EXECUTIONS.APPROVAL_COMMENT IS 'Optional comment from DBA approver (Story 7.4)';
