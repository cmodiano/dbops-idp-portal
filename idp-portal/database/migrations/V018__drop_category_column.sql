-- V018: Drop CATEGORY column from ACTIONS_CATALOG (Story 2.23)
-- Migrates existing categories to tags before dropping the column
-- Breaking change acceptable: internal API only

-- Step 1: Create tags for each distinct category (lowercase)
-- Using MERGE to avoid duplicates if tag already exists
MERGE INTO TAGS t
USING (
    SELECT DISTINCT LOWER(CATEGORY) AS tag_name
    FROM ACTIONS_CATALOG
    WHERE CATEGORY IS NOT NULL
) src
ON (t.NAME = src.tag_name)
WHEN NOT MATCHED THEN
    INSERT (NAME, CREATED_AT)
    VALUES (src.tag_name, SYSTIMESTAMP);

-- Step 2: Associate actions with their category-based tags
-- Skip if association already exists
MERGE INTO ACTION_TAGS at
USING (
    SELECT ac.ID AS action_id, t.ID AS tag_id
    FROM ACTIONS_CATALOG ac
    JOIN TAGS t ON t.NAME = LOWER(ac.CATEGORY)
    WHERE ac.CATEGORY IS NOT NULL
) src
ON (at.ACTION_ID = src.action_id AND at.TAG_ID = src.tag_id)
WHEN NOT MATCHED THEN
    INSERT (ACTION_ID, TAG_ID)
    VALUES (src.action_id, src.tag_id);

-- Step 3: Drop the CHECK constraint on CATEGORY
ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_CATALOG_CATEGORY;

-- Step 4: Drop the index on CATEGORY
DROP INDEX IDX_ACTIONS_CATALOG_CATEGORY;

-- Step 5: Make CATEGORY column nullable (keep column for rollback safety)
ALTER TABLE ACTIONS_CATALOG MODIFY CATEGORY NULL;
