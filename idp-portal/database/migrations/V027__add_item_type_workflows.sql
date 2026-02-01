-- V027: Add ITEM_TYPE column for action vs workflow distinction
-- Story 5.7 - Workflow = conteneur d'actions (pas de connecteur propre)
-- AC1: Typage action vs workflow ; AC2: Etapes workflow (referenced_action_id)

-- Add ITEM_TYPE column to ACTIONS_CATALOG (default 'action' for existing rows)
ALTER TABLE ACTIONS_CATALOG ADD ITEM_TYPE VARCHAR2(20) DEFAULT 'action' NOT NULL;

-- Constraint: only 'action' or 'workflow' allowed
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_CATALOG_ITEM_TYPE
    CHECK (ITEM_TYPE IN ('action', 'workflow'));

-- Index for filtering by item_type
CREATE INDEX IDX_ACTIONS_CATALOG_ITEM_TYPE ON ACTIONS_CATALOG(ITEM_TYPE);

-- Comments
COMMENT ON COLUMN ACTIONS_CATALOG.ITEM_TYPE IS 'Entry type: action (executable with connector) or workflow (container of action references, no connector)';

-- Note: Workflow steps use EXECUTION_STEPS CLOB with step_type discriminator:
-- For action: {"order":1,"name":"...","type":"execution","connector_type":"aap",...}
-- For workflow: {"order":1,"name":"...","step_type":"action_reference","referenced_action_id":42}
-- The step_type field distinguishes connector steps from action reference steps.
