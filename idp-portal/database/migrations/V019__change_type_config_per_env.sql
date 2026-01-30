-- V019: Change type config per environment (Story 2.24)
-- Migrate CHANGE_TYPE_CONFIG from env->"pre_approved" to env->{required, change_model_code}.
-- Report action-level CHANGE_MODEL_CODE onto envs that had pre_approved; then drop column CHANGE_MODEL_CODE.

-- Step 1: Update CHANGE_TYPE_CONFIG to new format per row (legacy only; preserve NULL; skip rows already in new format)
-- Old: {"DEV":"pre_approved","PROD":"pre_approved"}, CHANGE_MODEL_CODE = "1516B"
-- New: {"DEV":{"required":true,"change_model_code":"1516B"},"PROD":{"required":true,"change_model_code":"1516B"}}
-- If value is already object (new format), copy as-is. If CHANGE_TYPE_CONFIG is NULL, leave NULL (do not set to '{}').
DECLARE
  v_id NUMBER;
  v_old CLOB;
  v_code VARCHAR2(50);
  v_new CLOB;
  j_old JSON_OBJECT_T;
  j_new JSON_OBJECT_T;
  j_env JSON_OBJECT_T;
  v_keys JSON_KEY_LIST;
  v_key VARCHAR2(256);
  v_val VARCHAR2(100);
  i PLS_INTEGER;
BEGIN
  FOR r IN (SELECT id, change_type_config, change_model_code FROM ACTIONS_CATALOG) LOOP
    v_id := r.id;
    v_old := r.change_type_config;
    v_code := TRIM(r.change_model_code);
    j_new := JSON_OBJECT_T();

    IF v_old IS NOT NULL AND LENGTH(TRIM(v_old)) > 0 THEN
      BEGIN
        j_old := JSON_OBJECT_T.PARSE(v_old);
        v_keys := j_old.get_keys();
        IF v_keys IS NOT NULL THEN
          FOR i IN 1..v_keys.COUNT LOOP
            v_key := v_keys(i);
            j_env := j_old.get_Object(v_key);
            IF j_env IS NOT NULL THEN
              -- Already new format (value is object): copy as-is, do not overwrite
              j_new.put(v_key, j_env);
            ELSE
              -- Legacy format (value is string)
              v_val := LOWER(TRIM(NVL(j_old.get_string(v_key), '')));
              j_env := JSON_OBJECT_T();
              IF v_val IN ('pre_approved', 'cab') AND v_code IS NOT NULL AND LENGTH(v_code) > 0 THEN
                j_env.put('required', TRUE);
                j_env.put('change_model_code', v_code);
              ELSE
                j_env.put('required', FALSE);
              END IF;
              j_new.put(v_key, j_env);
            END IF;
          END LOOP;
        END IF;
      EXCEPTION
        WHEN OTHERS THEN
          j_new := JSON_OBJECT_T();
      END;

      -- Only UPDATE when we had legacy content (or valid parsed content); preserves NULL for rows with NULL change_type_config
      UPDATE ACTIONS_CATALOG
      SET CHANGE_TYPE_CONFIG = j_new.to_clob
      WHERE id = v_id;
    END IF;
  END LOOP;
  COMMIT;
END;
/

-- Step 2: Drop action-level CHANGE_MODEL_CODE column
ALTER TABLE ACTIONS_CATALOG DROP COLUMN CHANGE_MODEL_CODE;

-- Document new format
COMMENT ON COLUMN ACTIONS_CATALOG.CHANGE_TYPE_CONFIG IS 'JSON per env: {"PROD":{"required":true,"change_model_code":"1516B"},"DEV":{"required":false}}. required=true implies change_model_code required, alphanumeric max 50 (Story 2.24).';
