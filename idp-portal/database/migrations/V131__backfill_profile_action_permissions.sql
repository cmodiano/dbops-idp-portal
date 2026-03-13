-- V131: Backfill PROFILE_ACTION_ALLOWLIST, PROFILE_ACTION_TAG_PATTERNS, PROFILE_ACTION_ENVS
-- Story 78.11 — Normalisation des permissions action de profil
--
-- Lit chaque PROFILE_ACTION_PERMISSIONS, parse les JSON arrays via JSON_TABLE,
-- et insère dans les 3 tables normalisées.
-- Idempotent : DELETE + INSERT par PROFILE_ID (ré-exécution sans doublon).

DECLARE
    v_batch_count   NUMBER := 0;

    CURSOR c_perms IS
        SELECT PROFILE_ID, ACTION_IDS_JSON, TAG_PATTERNS_JSON, ENVIRONMENTS_JSON
        FROM PROFILE_ACTION_PERMISSIONS;

BEGIN
    FOR p IN c_perms LOOP
        -- Idempotent: remove existing normalized data for this profile
        DELETE FROM PROFILE_ACTION_ALLOWLIST WHERE PROFILE_ID = p.PROFILE_ID;
        DELETE FROM PROFILE_ACTION_TAG_PATTERNS WHERE PROFILE_ID = p.PROFILE_ID;
        DELETE FROM PROFILE_ACTION_ENVS WHERE PROFILE_ID = p.PROFILE_ID;

        -- Backfill ACTION_IDS_JSON → PROFILE_ACTION_ALLOWLIST
        IF p.ACTION_IDS_JSON IS NOT NULL
           AND DBMS_LOB.GETLENGTH(p.ACTION_IDS_JSON) > 2 THEN
            INSERT INTO PROFILE_ACTION_ALLOWLIST (PROFILE_ID, ACTION_ID)
            SELECT DISTINCT p.PROFILE_ID, jt.action_id
            FROM JSON_TABLE(p.ACTION_IDS_JSON, '$[*]'
                COLUMNS (action_id NUMBER PATH '$')
            ) jt
            WHERE jt.action_id IS NOT NULL;
        END IF;

        -- Backfill TAG_PATTERNS_JSON → PROFILE_ACTION_TAG_PATTERNS
        IF p.TAG_PATTERNS_JSON IS NOT NULL
           AND DBMS_LOB.GETLENGTH(p.TAG_PATTERNS_JSON) > 2 THEN
            INSERT INTO PROFILE_ACTION_TAG_PATTERNS (PROFILE_ID, TAG_PATTERN)
            SELECT DISTINCT p.PROFILE_ID, jt.tag_pattern
            FROM JSON_TABLE(p.TAG_PATTERNS_JSON, '$[*]'
                COLUMNS (tag_pattern VARCHAR2(255) PATH '$')
            ) jt
            WHERE jt.tag_pattern IS NOT NULL;
        END IF;

        -- Backfill ENVIRONMENTS_JSON → PROFILE_ACTION_ENVS
        IF p.ENVIRONMENTS_JSON IS NOT NULL
           AND DBMS_LOB.GETLENGTH(p.ENVIRONMENTS_JSON) > 2 THEN
            INSERT INTO PROFILE_ACTION_ENVS (PROFILE_ID, ENVIRONMENT)
            SELECT DISTINCT p.PROFILE_ID, jt.environment
            FROM JSON_TABLE(p.ENVIRONMENTS_JSON, '$[*]'
                COLUMNS (environment VARCHAR2(255) PATH '$')
            ) jt
            WHERE jt.environment IS NOT NULL;
        END IF;

        -- Batch commit every 100 profiles
        v_batch_count := v_batch_count + 1;
        IF MOD(v_batch_count, 100) = 0 THEN
            COMMIT;
        END IF;
    END LOOP;

    -- Final commit for remaining rows
    COMMIT;
END;
/
