-- V037: Make ENGINE and PLATFORM nullable for workflows (Story 5.7)
-- Workflows don't have engines or platforms since they're containers of actions
-- This allows creating workflows without ENGINE/PLATFORM while keeping them required for actions

-- Make ENGINE nullable (workflows don't have engines)
ALTER TABLE ACTIONS_CATALOG MODIFY ENGINE VARCHAR2(50) NULL;

-- Make PLATFORM nullable (workflows don't have platforms)
ALTER TABLE ACTIONS_CATALOG MODIFY PLATFORM VARCHAR2(50) NULL;

-- Update constraint to allow NULL for ENGINE (workflows)
-- Drop existing constraint and recreate it to allow NULL
ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_CATALOG_ENGINE;
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_CATALOG_ENGINE 
    CHECK (ENGINE IS NULL OR ENGINE IN ('Oracle', 'SQL Server', 'DB2'));

-- Update constraint to allow NULL for PLATFORM (workflows)
-- Drop existing constraint and recreate it to allow NULL
ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_CATALOG_PLATFORM;
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_CATALOG_PLATFORM 
    CHECK (PLATFORM IS NULL OR PLATFORM IN ('AAP', 'GitHub Actions', 'Azure DevOps', 'Terraform'));

-- Add check constraint to ensure actions have ENGINE and PLATFORM
-- Workflows (ITEM_TYPE='workflow') can have NULL ENGINE and PLATFORM
-- Actions (ITEM_TYPE='action') must have ENGINE and PLATFORM
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_CATALOG_ACTION_REQUIRES_ENGINE_PLATFORM
    CHECK (
        (ITEM_TYPE = 'workflow') OR 
        (ITEM_TYPE = 'action' AND ENGINE IS NOT NULL AND PLATFORM IS NOT NULL)
    );

-- Comments
COMMENT ON COLUMN ACTIONS_CATALOG.ENGINE IS 'Database engine (Oracle, SQL Server, DB2). Required for actions, NULL for workflows.';
COMMENT ON COLUMN ACTIONS_CATALOG.PLATFORM IS 'Execution platform (AAP, GitHub Actions, Azure DevOps, Terraform). Required for actions, NULL for workflows.';
