-- V050: Drop CHECK constraint on ACTIONS_CATALOG.ENGINE (Story 13.7)
-- Engine values are now validated against REF_ENGINES table via application logic
-- This allows adding new engines without database migrations

-- Drop the fixed CHECK constraint on ENGINE
ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_CATALOG_ENGINE;

-- Update CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM to remove ENGINE validation
-- Keep the constraint that actions (non-workflows) require ENGINE and PLATFORM to be NOT NULL
-- But remove the fixed value check - validation will be done against REF_ENGINES table in application
ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM;

-- Recreate the constraint without fixed ENGINE/PLATFORM values
-- Actions must have ENGINE and PLATFORM, workflows can have NULL
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM
    CHECK (
        (ITEM_TYPE = 'workflow') OR 
        (ITEM_TYPE = 'action' AND ENGINE IS NOT NULL AND PLATFORM IS NOT NULL)
    );

-- Comments
COMMENT ON COLUMN ACTIONS_CATALOG.ENGINE IS 'Database engine code (must exist in REF_ENGINES.CODE). Required for actions, NULL for workflows. Validated by application logic.';
