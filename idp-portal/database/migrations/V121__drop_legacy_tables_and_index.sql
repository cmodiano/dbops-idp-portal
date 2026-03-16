-- V121: Drop legacy tables and obsolete index (schema cleanup)
-- Ref: docs/backend/migration/schema-codepath-orphan-analysis.md
--
-- 1. EXECUTION_LOG (V006) — table legacy, remplacée par EXECUTIONS (V023)
--    Aucun modèle Django, dashboard utilise Execution.objects
-- 2. USER_PERMISSIONS (V005) — RBAC legacy, remplacé par PROFILES + PROFILE_ACTION_PERMISSIONS (Story 2-14)
--    Aucun modèle Django, RBAC via CatalogRBACService
-- 3. IDX_EXECUTIONS_PENDING_APPROVAL — index sur statut déprécié (ADR-007)
--    PENDING_APPROVAL n'est plus utilisé, approbations via ExecutionStep gates

-- Drop obsolete index on EXECUTIONS (ORA-01418 = -1418)
BEGIN
    EXECUTE IMMEDIATE 'DROP INDEX IDX_EXECUTIONS_PENDING_APPROVAL';
EXCEPTION WHEN OTHERS THEN IF SQLCODE = -1418 THEN NULL; ELSE RAISE; END IF;
END;
/

-- Drop legacy EXECUTION_LOG table (ORA-00942 = -942)
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE EXECUTION_LOG';
EXCEPTION WHEN OTHERS THEN IF SQLCODE = -942 THEN NULL; ELSE RAISE; END IF;
END;
/

-- Drop legacy USER_PERMISSIONS table (ORA-00942 = -942)
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE USER_PERMISSIONS';
EXCEPTION WHEN OTHERS THEN IF SQLCODE = -942 THEN NULL; ELSE RAISE; END IF;
END;
/
