-- Story 2.14: Remove legacy RBAC per action column
-- RBAC is now managed via dynamic profiles (Stories 2-9 to 2-13)
-- AC1: Drop rbac_policies column from ACTIONS_CATALOG
-- Task 1.2: No view or FK references RBAC_POLICIES (only ACTIONS_CATALOG had this column).

ALTER TABLE ACTIONS_CATALOG DROP COLUMN RBAC_POLICIES;
