-- Add CONFIG_STEP_ID column to EXECUTION_STEPS
-- Stores the workflow config's step_id (UUID) for reliable matching between
-- ExecutionStep DB records and their workflow step definitions.
-- Replaces fragile name-based matching that fails when step name is null.

ALTER TABLE EXECUTION_STEPS ADD (
    CONFIG_STEP_ID VARCHAR2(255)
);

CREATE INDEX IDX_EXEC_STEPS_CONFIG_STEP_ID ON EXECUTION_STEPS(CONFIG_STEP_ID);

COMMENT ON COLUMN EXECUTION_STEPS.CONFIG_STEP_ID IS 'step_id from action.execution_steps config (UUID). Used to reliably match an ExecutionStep back to its workflow definition. V116.';
