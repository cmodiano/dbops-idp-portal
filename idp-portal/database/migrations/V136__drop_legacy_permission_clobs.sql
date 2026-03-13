-- V136: Drop legacy CLOB permission columns (Story 78.15)
--
-- Phase E — Contract phase: remove legacy JSON CLOB columns from permission tables.
-- Tables PROFILE_ACTION_ALLOWLIST, PROFILE_ACTION_TAG_PATTERNS, PROFILE_ACTION_ENVS,
-- PROFILE_TARGET_ALLOWLIST, PROFILE_TARGET_PATTERNS, PROFILE_TARGET_ATTRIBUTE_FILTERS,
-- PROFILE_TARGET_EXCLUSIONS are now the single source of truth (78.11, 78.12 done).
--
-- Prerequisites (must be validated before running this migration):
--   - Feature flag PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED = True in production
--   - Feature flag PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED = True in production
--   - Parity check check_profile_action_permission_parity   → zero divergence
--   - Parity check check_profile_target_permission_parity    → zero divergence
--   - Soak period: feature flags active for >= 1 sprint (2 weeks recommended)
--
-- Rollback: see database/scripts/rollback_V136_legacy_permission_clobs.sql

-- ============================================================
-- PROFILE_ACTION_PERMISSIONS — Drop CLOB columns
-- ============================================================

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_ACTION_PERMISSIONS DROP COLUMN ACTION_IDS_JSON';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;  -- ORA-00904: column does not exist — idempotent
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_ACTION_PERMISSIONS DROP COLUMN TAG_PATTERNS_JSON';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_ACTION_PERMISSIONS DROP COLUMN ENVIRONMENTS_JSON';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

-- ============================================================
-- PROFILE_TARGET_PERMISSIONS — Drop CLOB columns
-- ============================================================

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS DROP COLUMN TARGET_NAMES_JSON';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS DROP COLUMN TARGET_PATTERNS_JSON';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS DROP COLUMN FILTER_BY_ATTRIBUTE_JSON';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS DROP COLUMN EXCLUSION_PATTERNS_JSON';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

-- ============================================================
-- EXECUTIONS — Drop deprecated approval columns (78.14 scope)
--
-- APPROVED_BY, APPROVED_AT, APPROVAL_COMMENT deprecated in V135.
-- Source of truth: EXECUTION_STEPS with step_type='approval'.
-- dashboard/operations_approbations must read from EXECUTION_STEPS.
-- ============================================================

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS DROP COLUMN APPROVED_BY';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS DROP COLUMN APPROVED_AT';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS DROP COLUMN APPROVAL_COMMENT';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -904 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/
