-- V009: Remove CAB from CHANGE_TYPE_CONFIG (Story 2.8 - Suppression rail CAB, simplification ServiceNow)
-- Converts all "cab" (any case: cab, CAB, Cab) to "pre_approved" in CHANGE_TYPE_CONFIG CLOB. Idempotent.

UPDATE ACTIONS_CATALOG
SET CHANGE_TYPE_CONFIG = REGEXP_REPLACE(CHANGE_TYPE_CONFIG, '"cab"', '"pre_approved"', 1, 0, 'i')
WHERE CHANGE_TYPE_CONFIG IS NOT NULL
  AND REGEXP_LIKE(CHANGE_TYPE_CONFIG, '"cab"', 'i');

-- Document that only pre_approved is valid (Story 2.8, AC2)
COMMENT ON COLUMN ACTIONS_CATALOG.CHANGE_TYPE_CONFIG IS 'JSON object mapping environment to change type. Example: {"DEV":"pre_approved","STAGING":"pre_approved","PROD":"pre_approved"}. Valid type: pre_approved only (Story 2.8: CAB removed).';

-- Record migration (idempotent)
MERGE INTO SCHEMA_VERSION D
USING (SELECT 'V009' AS V FROM DUAL) S ON (D.VERSION = S.V)
WHEN NOT MATCHED THEN INSERT (VERSION) VALUES (S.V);
