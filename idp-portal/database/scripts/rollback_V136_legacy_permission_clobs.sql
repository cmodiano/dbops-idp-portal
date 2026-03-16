-- Rollback script for V136__drop_legacy_permission_clobs.sql (Story 78.15)
--
-- PURPOSE: Emergency rollback — recreate CLOB columns dropped by V136.
--
-- WHEN TO USE: Only if V136 must be reverted after a production incident
--   and the previous application version (pre-78.15 code) must be redeployed.
--
-- ROLLBACK PROCEDURE:
--   1. Stop application servers (prevent new writes)
--   2. Execute this script on the Oracle database
--   3. Restore the pre-78.15 application version (Docker image / deployment)
--      IMPORTANT: The feature flags PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED and
--      PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED were removed from settings.py in
--      story 78.15. They only exist in the pre-78.15 codebase. Step 3 (restore pre-78.15
--      image) is therefore required BEFORE step 4 can work.
--   4. Set feature flags in the restored pre-78.15 environment:
--        PROFILE_ACTION_PERMISSIONS_NORMALIZED_ENABLED = True
--        PROFILE_TARGET_PERMISSIONS_NORMALIZED_ENABLED = True
--      (to keep dual-write active in the legacy code path and avoid data loss)
--   5. Backfill CLOB columns from normalized tables (manual step):
--        The normalized tables (PROFILE_ACTION_ALLOWLIST, PROFILE_ACTION_TAG_PATTERNS,
--        PROFILE_ACTION_ENVS, PROFILE_TARGET_ALLOWLIST, PROFILE_TARGET_PATTERNS,
--        PROFILE_TARGET_ATTRIBUTE_FILTERS, PROFILE_TARGET_EXCLUSIONS) remain intact
--        and hold authoritative data. No automated backfill script exists since the
--        CLOB columns were the legacy representation — the pre-78.15 application code
--        will write CLOB values on the next permission save for each profile.
--   6. Validate parity checks before re-enabling reads from CLOB columns.
--   7. Restart application servers.
--
-- NOTE: Recreated columns are NULLABLE CLOBs — no data is restored automatically.
--   The normalized tables remain intact and continue to hold authoritative data.

-- ============================================================
-- PROFILE_ACTION_PERMISSIONS — Recreate CLOB columns
-- ============================================================

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_ACTION_PERMISSIONS ADD ACTION_IDS_JSON CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;  -- ORA-01430: column already exists
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_ACTION_PERMISSIONS ADD TAG_PATTERNS_JSON CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_ACTION_PERMISSIONS ADD ENVIRONMENTS_JSON CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

-- ============================================================
-- PROFILE_TARGET_PERMISSIONS — Recreate CLOB columns
-- ============================================================

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD TARGET_NAMES_JSON CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD TARGET_PATTERNS_JSON CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD FILTER_BY_ATTRIBUTE_JSON CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD EXCLUSION_PATTERNS_JSON CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

-- ============================================================
-- EXECUTIONS — Recreate deprecated approval columns
-- ============================================================

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS ADD APPROVED_BY VARCHAR2(255)';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS ADD APPROVED_AT TIMESTAMP WITH TIME ZONE';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS ADD APPROVAL_COMMENT CLOB';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -1430 THEN NULL;
    ELSE RAISE;
    END IF;
END;
/

PROMPT Rollback V136 complete. Columns recreated (NULL). Follow manual backfill procedure before restarting application.
