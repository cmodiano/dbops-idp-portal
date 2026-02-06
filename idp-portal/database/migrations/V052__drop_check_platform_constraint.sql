-- V052: Drop CHECK constraint on ACTIONS_CATALOG.PLATFORM (Story 13.7)
-- Platform values are now validated against REF_PLATFORMS table via application logic
-- This allows adding new platforms without database migrations

-- Drop the fixed CHECK constraint on PLATFORM
ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_CATALOG_PLATFORM;

-- Update CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM to remove PLATFORM validation
-- Keep the constraint that actions (non-workflows) require ENGINE and PLATFORM to be NOT NULL
-- But remove the fixed value check - validation will be done against REF_PLATFORMS table in application
ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM;

-- Recreate the constraint without fixed ENGINE/PLATFORM values
-- Actions must have ENGINE and PLATFORM, workflows can have NULL
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM
    CHECK (
        (ITEM_TYPE = 'workflow') OR 
        (ITEM_TYPE = 'action' AND ENGINE IS NOT NULL AND PLATFORM IS NOT NULL)
    );

-- Comments
COMMENT ON COLUMN ACTIONS_CATALOG.PLATFORM IS 'Execution platform code (must exist in REF_PLATFORMS.CODE). Required for actions, NULL for workflows. Validated by application logic.';
