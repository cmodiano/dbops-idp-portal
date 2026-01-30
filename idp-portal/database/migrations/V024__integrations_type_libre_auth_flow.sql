-- Migration V024: Integrations - type libre + auth_flow
-- Story 4.9 - Type libre, flow auth (token/basic/pat), upload icône
-- AC1, AC5, AC6: Type libre (VARCHAR), auth_flow (enum), rétrocompatibilité

-- 1. Drop TYPE CHECK constraint to allow free-form type
ALTER TABLE INTEGRATIONS DROP CONSTRAINT CK_INTEGRATIONS_TYPE;

-- 2. Modify TYPE column to allow longer free-form platform names (already VARCHAR2(50), extend to 100)
ALTER TABLE INTEGRATIONS MODIFY TYPE VARCHAR2(100) NOT NULL;

-- 3. Add AUTH_FLOW column with enum constraint (token, basic, basic_then_token, pat)
-- Nullable for backward compatibility with existing integrations
ALTER TABLE INTEGRATIONS ADD AUTH_FLOW VARCHAR2(50);

ALTER TABLE INTEGRATIONS ADD CONSTRAINT CK_INTEGRATIONS_AUTH_FLOW 
    CHECK (AUTH_FLOW IS NULL OR AUTH_FLOW IN ('token', 'basic', 'basic_then_token', 'pat'));

-- 4. Data migration: existing integrations keep their type values (already strings)
-- No data conversion needed - types are already stored as strings (aap, servicenow, etc.)
-- AUTH_FLOW defaults to NULL for existing integrations (acceptable per AC5)
-- Impact: Execution engine will need to handle NULL auth_flow (e.g., fallback to 'token' flow by default)
-- Existing integrations can be updated later via API to set explicit auth_flow value

-- 5. Keep IDX_INTEGRATIONS_TYPE index for performance (type queries still useful)
-- No action needed - index remains valid on VARCHAR2 column

-- Comments
COMMENT ON COLUMN INTEGRATIONS.TYPE IS 'Integration type: free-form platform name (1-100 chars)';
COMMENT ON COLUMN INTEGRATIONS.AUTH_FLOW IS 'Authentication flow: token, basic, basic_then_token, pat (nullable for backward compatibility)';
