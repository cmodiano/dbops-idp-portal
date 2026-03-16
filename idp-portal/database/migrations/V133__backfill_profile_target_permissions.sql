-- V133: Backfill PROFILE_TARGET_ALLOWLIST, PROFILE_TARGET_PATTERNS, PROFILE_TARGET_ATTRIBUTE_FILTERS, PROFILE_TARGET_EXCLUSIONS
-- Story 78.12 — Normalisation des permissions target de profil
--
-- Lit chaque PROFILE_TARGET_PERMISSIONS, parse les JSON arrays/dict via JSON_TABLE,
-- et insère dans les 4 tables normalisées.
-- Idempotent : DELETE + INSERT par PROFILE_ID (ré-exécution sans doublon).
--
-- Si les colonnes CLOB n'existent pas (baseline ou post-V136), le backfill est ignoré (no-op).
-- Utilise EXECUTE IMMEDIATE pour éviter ORA-00904 à la compilation du curseur.

DECLARE
    v_has_clob_cols NUMBER := 0;
    v_sql           CLOB;
BEGIN
    -- Skip if CLOB columns were dropped (baseline or post-V136) — no data to migrate
    SELECT COUNT(*) INTO v_has_clob_cols
    FROM USER_TAB_COLUMNS
    WHERE TABLE_NAME = 'PROFILE_TARGET_PERMISSIONS'
      AND COLUMN_NAME = 'EXCLUSION_PATTERNS_JSON';

    IF v_has_clob_cols = 0 THEN
        NULL;  /* no-op */
    ELSE
        v_sql := '
DECLARE
    v_batch_count   NUMBER := 0;
    CURSOR c_perms IS
        SELECT PROFILE_ID, TARGET_NAMES_JSON, TARGET_PATTERNS_JSON,
               FILTER_BY_ATTRIBUTE_JSON, EXCLUSION_PATTERNS_JSON
        FROM PROFILE_TARGET_PERMISSIONS;
BEGIN
    FOR p IN c_perms LOOP
        DELETE FROM PROFILE_TARGET_ALLOWLIST WHERE PROFILE_ID = p.PROFILE_ID;
        DELETE FROM PROFILE_TARGET_PATTERNS WHERE PROFILE_ID = p.PROFILE_ID;
        DELETE FROM PROFILE_TARGET_ATTRIBUTE_FILTERS WHERE PROFILE_ID = p.PROFILE_ID;
        DELETE FROM PROFILE_TARGET_EXCLUSIONS WHERE PROFILE_ID = p.PROFILE_ID;

        IF p.TARGET_NAMES_JSON IS NOT NULL AND DBMS_LOB.GETLENGTH(p.TARGET_NAMES_JSON) > 2 THEN
            INSERT INTO PROFILE_TARGET_ALLOWLIST (PROFILE_ID, TARGET_NAME)
            SELECT DISTINCT p.PROFILE_ID, jt.target_name
            FROM JSON_TABLE(p.TARGET_NAMES_JSON, ''$[*]''
                COLUMNS (target_name VARCHAR2(255) PATH ''$'')
            ) jt
            WHERE jt.target_name IS NOT NULL;
        END IF;

        IF p.TARGET_PATTERNS_JSON IS NOT NULL AND DBMS_LOB.GETLENGTH(p.TARGET_PATTERNS_JSON) > 2 THEN
            INSERT INTO PROFILE_TARGET_PATTERNS (PROFILE_ID, PATTERN)
            SELECT DISTINCT p.PROFILE_ID, jt.pattern
            FROM JSON_TABLE(p.TARGET_PATTERNS_JSON, ''$[*]''
                COLUMNS (pattern VARCHAR2(255) PATH ''$'')
            ) jt
            WHERE jt.pattern IS NOT NULL;
        END IF;

        IF p.FILTER_BY_ATTRIBUTE_JSON IS NOT NULL AND DBMS_LOB.GETLENGTH(p.FILTER_BY_ATTRIBUTE_JSON) > 2 THEN
            DECLARE
                v_obj   JSON_OBJECT_T;
                v_keys  JSON_KEY_LIST;
                v_arr   JSON_ARRAY_T;
                v_key   VARCHAR2(255);
                v_val   VARCHAR2(255);
            BEGIN
                v_obj := JSON_OBJECT_T.parse(p.FILTER_BY_ATTRIBUTE_JSON);
                v_keys := v_obj.get_keys();
                FOR i IN 1 .. v_keys.COUNT LOOP
                    v_key := v_keys(i);
                    IF v_obj.get(v_key).is_array() THEN
                        v_arr := v_obj.get_array(v_key);
                        FOR j IN 0 .. v_arr.get_size() - 1 LOOP
                            v_val := v_arr.get_string(j);
                            IF v_val IS NOT NULL THEN
                                BEGIN
                                    INSERT INTO PROFILE_TARGET_ATTRIBUTE_FILTERS
                                        (PROFILE_ID, ATTRIBUTE_KEY, ATTRIBUTE_VALUE)
                                    VALUES (p.PROFILE_ID, v_key, v_val);
                                EXCEPTION
                                    WHEN DUP_VAL_ON_INDEX THEN NULL;
                                END;
                            END IF;
                        END LOOP;
                    END IF;
                END LOOP;
            END;
        END IF;

        IF p.EXCLUSION_PATTERNS_JSON IS NOT NULL AND DBMS_LOB.GETLENGTH(p.EXCLUSION_PATTERNS_JSON) > 2 THEN
            INSERT INTO PROFILE_TARGET_EXCLUSIONS (PROFILE_ID, EXCLUSION_PATTERN)
            SELECT DISTINCT p.PROFILE_ID, jt.exclusion_pattern
            FROM JSON_TABLE(p.EXCLUSION_PATTERNS_JSON, ''$[*]''
                COLUMNS (exclusion_pattern VARCHAR2(255) PATH ''$'')
            ) jt
            WHERE jt.exclusion_pattern IS NOT NULL;
        END IF;

        v_batch_count := v_batch_count + 1;
        IF MOD(v_batch_count, 100) = 0 THEN
            COMMIT;
        END IF;
    END LOOP;
    COMMIT;
END;
';
        EXECUTE IMMEDIATE v_sql;
    END IF;
END;
/
