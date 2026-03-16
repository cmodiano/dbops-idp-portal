-- V129: Contraintes strictes sur les tables WORKFLOW_DEFINITIONS / WORKFLOW_STEPS
-- Story 78.10, AC5 — À exécuter APRÈS backfill (V128) réussi et parity check validé
--
-- En développement, cette migration peut être appliquée immédiatement après V128.
-- En production, ne l'appliquer QU'APRÈS validation via check_workflow_definition_parity.

-- WORKFLOW_DEFINITIONS: ACTION_ID NOT NULL + UNIQUE
ALTER TABLE WORKFLOW_DEFINITIONS MODIFY ACTION_ID NOT NULL;
ALTER TABLE WORKFLOW_DEFINITIONS ADD CONSTRAINT UK_WF_DEF_ACTION_ID UNIQUE (ACTION_ID);

-- WORKFLOW_STEPS: composite unique (WORKFLOW_DEFINITION_ID, STEP_ID)
ALTER TABLE WORKFLOW_STEPS ADD CONSTRAINT UK_WF_STEPS_DEF_STEP_ID UNIQUE (WORKFLOW_DEFINITION_ID, STEP_ID);

-- WORKFLOW_STEPS: CHECK constraint on STEP_TYPE
ALTER TABLE WORKFLOW_STEPS ADD CONSTRAINT CK_WF_STEPS_STEP_TYPE CHECK (
    STEP_TYPE IN ('platform', 'service_call', 'http_request', 'evaluation', 'gate', 'schedule_execution')
);
