-- Story 57.15: Add audit type for workflow schedule step
INSERT INTO REF_AUDIT_ACTION_TYPES (CODE, LABEL) VALUES
    ('WORKFLOW_STEP_SCHEDULE_CREATED', 'Workflow Step Schedule Created');
