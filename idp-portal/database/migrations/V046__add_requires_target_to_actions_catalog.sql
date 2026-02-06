-- V046: Add REQUIRES_TARGET column to ACTIONS_CATALOG
-- Story 13.2, Task 7: Support for actions that don't require target selection
-- Default is 1 (true) - most actions require a target

-- Add REQUIRES_TARGET column with default value 1 (true)
ALTER TABLE ACTIONS_CATALOG ADD (
    REQUIRES_TARGET NUMBER(1) DEFAULT 1 NOT NULL
);

-- Add comment for documentation
COMMENT ON COLUMN ACTIONS_CATALOG.REQUIRES_TARGET IS
    'Story 13.2, AC3: Whether action requires target selection (1=true, 0=false). Default is true.';
