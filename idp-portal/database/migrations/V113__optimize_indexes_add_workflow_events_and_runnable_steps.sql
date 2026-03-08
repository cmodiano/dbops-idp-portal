-- V113: Optimize indexes + add WORKFLOW_EVENTS and RUNNABLE_STEPS tables
--
-- Part 1: Missing indexes identified from query pattern analysis
-- Part 2: WORKFLOW_EVENTS — event sourcing table for real-time UI sync
-- Part 3: RUNNABLE_STEPS — work queue of steps ready for execution
--
-- Story: Schema optimization sprint

-- ===========================================================================
-- PART 1: Missing indexes
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- EXECUTIONS: GLOBAL index on STATUS for dashboard aggregate queries
-- (existing LOCAL indexes require created_at partition pruning)
-- Dashboard views count FAILED/COMPLETED across all partitions without date filter
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_EXECUTIONS_STATUS_GLOBAL ON EXECUTIONS(STATUS);

-- ---------------------------------------------------------------------------
-- EXECUTIONS: GLOBAL index on USER_ID for user-scoped listing without date filter
-- Covers: apply_scope_filter(), list_by_user() when no date range specified
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_EXECUTIONS_USER_GLOBAL ON EXECUTIONS(USER_ID);

-- ---------------------------------------------------------------------------
-- EXECUTIONS: GLOBAL index on ENVIRONMENT for audit cross-partition lookups
-- Covers: audit/views.py filtering by environment across all partitions
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_EXECUTIONS_ENVIRONMENT_GLOBAL ON EXECUTIONS(ENVIRONMENT);

-- ---------------------------------------------------------------------------
-- EXECUTIONS: GLOBAL function-based index on SERVICENOW_CHANGE_ID for ServiceNow lookups
-- Sparse: only rows with a non-NULL change ID are indexed (Oracle function-based)
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_EXECUTIONS_SN_CHANGE_ID ON EXECUTIONS(
    CASE WHEN SERVICENOW_CHANGE_ID IS NOT NULL THEN SERVICENOW_CHANGE_ID END
);

-- ---------------------------------------------------------------------------
-- EXECUTION_STEPS: GLOBAL index on STATUS for cross-partition queries
-- Covers: approval_views checking WAITING steps, step dispatcher queries
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_EXEC_STEPS_STATUS_GLOBAL ON EXECUTION_STEPS(STATUS);

-- ---------------------------------------------------------------------------
-- EXECUTION_STEPS: function-based index on PLATFORM_JOB_ID for polling task lookups
-- Covers: polling.py filter by platform_job_id (Oracle function-based sparse)
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_EXEC_STEPS_PLATFORM_JOB ON EXECUTION_STEPS(
    CASE WHEN PLATFORM_JOB_ID IS NOT NULL THEN PLATFORM_JOB_ID END
);

-- ---------------------------------------------------------------------------
-- SCHEDULED_EXECUTIONS: composite index for list_pending query
-- Covers: ScheduledExecutionManager.list_pending() filtering status + scheduled_at
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_SCHEDULED_EXEC_PENDING ON SCHEDULED_EXECUTIONS(STATUS, SCHEDULED_AT);

-- ---------------------------------------------------------------------------
-- EXECUTION_TARGETS: index on TARGET_ID for mutex/conflict checking
-- Covers: mutex queries that look up running executions by target
-- ---------------------------------------------------------------------------
CREATE INDEX IDX_EXEC_TARGETS_TARGET_ID ON EXECUTION_TARGETS(TARGET_ID);


-- ===========================================================================
-- PART 2: WORKFLOW_EVENTS — Event sourcing for real-time UI sync
-- ===========================================================================
-- Each state change in an execution or step produces an event row.
-- The UI subscribes via WebSocket and uses the sequence number to detect
-- missed events and request catch-up from this table.
-- Rows older than a configurable retention period are purged.
-- ---------------------------------------------------------------------------
CREATE TABLE WORKFLOW_EVENTS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    EXECUTION_ID    NUMBER NOT NULL,
    EVENT_TYPE      VARCHAR2(50) NOT NULL,
    ENTITY_TYPE     VARCHAR2(30) NOT NULL,
    ENTITY_ID       NUMBER NOT NULL,
    SEQUENCE_NUM    NUMBER NOT NULL,
    PAYLOAD         CLOB CHECK (PAYLOAD IS JSON),
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,

    CONSTRAINT FK_WORKFLOW_EVENTS_EXEC FOREIGN KEY (EXECUTION_ID)
        REFERENCES EXECUTIONS(ID) ON DELETE CASCADE,
    CONSTRAINT CK_WORKFLOW_EVENTS_EVENT_TYPE CHECK (
        EVENT_TYPE IN (
            'EXECUTION_STATUS_CHANGED',
            'STEP_STATUS_CHANGED',
            'STEP_OUTPUT_UPDATED',
            'STEP_STARTED',
            'STEP_COMPLETED',
            'STEP_FAILED',
            'APPROVAL_REQUESTED',
            'APPROVAL_GRANTED',
            'APPROVAL_REJECTED',
            'TARGET_ADDED',
            'EXECUTION_COMPLETED',
            'EXECUTION_FAILED'
        )
    ),
    CONSTRAINT CK_WORKFLOW_EVENTS_ENTITY_TYPE CHECK (
        ENTITY_TYPE IN ('execution', 'execution_step', 'execution_target')
    ),
    CONSTRAINT UK_WORKFLOW_EVENTS_EXEC_SEQ UNIQUE (EXECUTION_ID, SEQUENCE_NUM)
);

CREATE INDEX IDX_WORKFLOW_EVENTS_EXEC_CREATED ON WORKFLOW_EVENTS(EXECUTION_ID, CREATED_AT);
CREATE INDEX IDX_WORKFLOW_EVENTS_CREATED       ON WORKFLOW_EVENTS(CREATED_AT);
CREATE INDEX IDX_WORKFLOW_EVENTS_ENTITY        ON WORKFLOW_EVENTS(ENTITY_TYPE, ENTITY_ID);

COMMENT ON TABLE WORKFLOW_EVENTS IS 'Event sourcing table for real-time UI sync via WebSocket. Each state change produces a row. Rows purged after retention period.';
COMMENT ON COLUMN WORKFLOW_EVENTS.EXECUTION_ID IS 'FK to EXECUTIONS — scopes events to a single execution for WebSocket subscription.';
COMMENT ON COLUMN WORKFLOW_EVENTS.EVENT_TYPE IS 'Discriminator for event kind (status change, output update, approval, etc.).';
COMMENT ON COLUMN WORKFLOW_EVENTS.ENTITY_TYPE IS 'Type of entity that changed: execution, execution_step, or execution_target.';
COMMENT ON COLUMN WORKFLOW_EVENTS.ENTITY_ID IS 'PK of the changed entity (Execution.id, ExecutionStep.id, etc.).';
COMMENT ON COLUMN WORKFLOW_EVENTS.SEQUENCE_NUM IS 'Monotonically increasing per execution. Clients use this to detect gaps and request catch-up.';
COMMENT ON COLUMN WORKFLOW_EVENTS.PAYLOAD IS 'JSON snapshot of the change (new status, output diff, approval details, etc.).';
COMMENT ON COLUMN WORKFLOW_EVENTS.CREATED_AT IS 'Event timestamp. Used for retention purge.';


-- ===========================================================================
-- PART 3: RUNNABLE_STEPS — Work queue of steps ready for execution
-- ===========================================================================
-- When the workflow engine determines a step is eligible to run (all
-- prerequisites met, gates satisfied), it inserts a row here.
-- Workers claim rows by setting CLAIMED_AT + CLAIMED_BY, then transition
-- the ExecutionStep to RUNNING and delete the RUNNABLE_STEPS row.
-- This avoids scanning EXECUTION_STEPS for PENDING rows with met dependencies.
-- ---------------------------------------------------------------------------
CREATE TABLE RUNNABLE_STEPS (
    ID                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    EXECUTION_STEP_ID NUMBER NOT NULL,
    EXECUTION_ID      NUMBER NOT NULL,
    STEP_ORDER        NUMBER NOT NULL,
    STEP_TYPE         VARCHAR2(50) NOT NULL,
    PRIORITY          NUMBER DEFAULT 0 NOT NULL,
    ELIGIBLE_AT       TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    CLAIMED_AT        TIMESTAMP,
    CLAIMED_BY        VARCHAR2(255),
    CREATED_AT        TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,

    CONSTRAINT FK_RUNNABLE_STEPS_STEP FOREIGN KEY (EXECUTION_STEP_ID)
        REFERENCES EXECUTION_STEPS(ID) ON DELETE CASCADE,
    CONSTRAINT FK_RUNNABLE_STEPS_EXEC FOREIGN KEY (EXECUTION_ID)
        REFERENCES EXECUTIONS(ID) ON DELETE CASCADE,
    CONSTRAINT UK_RUNNABLE_STEPS_STEP UNIQUE (EXECUTION_STEP_ID)
);

-- Primary query: unclaimed steps ordered by priority then eligibility
CREATE INDEX IDX_RUNNABLE_STEPS_UNCLAIMED ON RUNNABLE_STEPS(CLAIMED_AT, PRIORITY, ELIGIBLE_AT);
-- Lookup by execution for workflow progress queries
CREATE INDEX IDX_RUNNABLE_STEPS_EXEC ON RUNNABLE_STEPS(EXECUTION_ID);

COMMENT ON TABLE RUNNABLE_STEPS IS 'Work queue of execution steps ready to run. Workers claim and process rows, then delete them. Avoids full-table scans of EXECUTION_STEPS.';
COMMENT ON COLUMN RUNNABLE_STEPS.EXECUTION_STEP_ID IS 'FK to EXECUTION_STEPS — the step to execute. Unique: a step can only be queued once.';
COMMENT ON COLUMN RUNNABLE_STEPS.EXECUTION_ID IS 'Denormalized FK to EXECUTIONS for fast per-execution queue queries.';
COMMENT ON COLUMN RUNNABLE_STEPS.STEP_ORDER IS 'Denormalized from EXECUTION_STEPS for ordering without join.';
COMMENT ON COLUMN RUNNABLE_STEPS.STEP_TYPE IS 'Denormalized from EXECUTION_STEPS for type-based worker routing.';
COMMENT ON COLUMN RUNNABLE_STEPS.PRIORITY IS 'Higher = higher priority. Default 0. Gate steps may get elevated priority.';
COMMENT ON COLUMN RUNNABLE_STEPS.ELIGIBLE_AT IS 'When the step became eligible. Used for FIFO ordering within same priority.';
COMMENT ON COLUMN RUNNABLE_STEPS.CLAIMED_AT IS 'NULL = unclaimed. Set by worker to claim the step (optimistic locking).';
COMMENT ON COLUMN RUNNABLE_STEPS.CLAIMED_BY IS 'Worker identifier that claimed this step (hostname, task_id, etc.).';
