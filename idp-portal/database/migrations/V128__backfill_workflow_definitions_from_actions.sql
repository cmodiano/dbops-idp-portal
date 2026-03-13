-- V128: Backfill WORKFLOW_DEFINITIONS depuis ACTIONS_CATALOG.EXECUTION_STEPS
-- Story 78.10 — Normalisation des définitions de workflow
--
-- Lit chaque ACTIONS_CATALOG avec ITEM_TYPE = 'workflow' et EXECUTION_STEPS IS NOT NULL,
-- parse le JSON via JSON_TABLE, et insère dans les 3 tables normalisées.
-- Idempotent : DELETE + INSERT par action_id (ré-exécution sans doublon).

DECLARE
    v_wf_def_id     NUMBER;
    v_step_db_id    NUMBER;
    v_to_step_db_id NUMBER;
    v_batch_count   NUMBER := 0;

    CURSOR c_workflows IS
        SELECT ID AS action_id, EXECUTION_STEPS
        FROM ACTIONS_CATALOG
        WHERE ITEM_TYPE = 'workflow'
          AND EXECUTION_STEPS IS NOT NULL
          AND DBMS_LOB.GETLENGTH(EXECUTION_STEPS) > 2;

    CURSOR c_steps(p_execution_steps CLOB) IS
        SELECT jt.*
        FROM JSON_TABLE(p_execution_steps, '$[*]'
            COLUMNS (
                step_order              NUMBER          PATH '$.order',
                step_id                 VARCHAR2(255)   PATH '$.step_id',
                step_name               VARCHAR2(255)   PATH '$.name',
                step_type               VARCHAR2(50)    PATH '$.step_type',
                referenced_action_id    NUMBER          PATH '$.referenced_action_id',
                integration_type        VARCHAR2(100)   PATH '$.integration_type',
                operation               VARCHAR2(255)   PATH '$.operation',
                input_mapping           CLOB            PATH '$.input_mapping',
                output_mapping          CLOB            PATH '$.output_mapping',
                condition_expr          CLOB            PATH '$.condition',
                retry_enabled           NUMBER          PATH '$.retry_enabled',
                retry_max_attempts      NUMBER          PATH '$.retry_max_attempts',
                retry_interval_seconds  NUMBER          PATH '$.retry_interval_seconds',
                retry_backoff_multiplier NUMBER         PATH '$.retry_backoff_multiplier',
                join_policy             VARCHAR2(50)    PATH '$.join_policy',
                on_success_step_ids     CLOB            PATH '$.on_success_step_ids',
                on_error_step_ids       CLOB            PATH '$.on_error_step_ids'
            )
        ) jt;

    TYPE t_step_row IS RECORD (
        step_id                 VARCHAR2(255),
        on_success_step_ids     CLOB,
        on_error_step_ids       CLOB,
        db_id                   NUMBER
    );
    TYPE t_step_list IS TABLE OF t_step_row INDEX BY PLS_INTEGER;
    v_steps t_step_list;
    v_idx   PLS_INTEGER;

    CURSOR c_edge_targets(p_step_ids_json CLOB) IS
        SELECT jt.target_step_id
        FROM JSON_TABLE(p_step_ids_json, '$[*]'
            COLUMNS (
                target_step_id VARCHAR2(255) PATH '$'
            )
        ) jt;

BEGIN
    FOR wf IN c_workflows LOOP
        -- Idempotent: remove existing data for this action
        DELETE FROM WORKFLOW_DEFINITIONS WHERE ACTION_ID = wf.action_id;

        -- Insert workflow definition
        INSERT INTO WORKFLOW_DEFINITIONS (ACTION_ID, VERSION, CREATED_AT, UPDATED_AT)
        VALUES (wf.action_id, 1,
                TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6'),
                TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6'))
        RETURNING ID INTO v_wf_def_id;

        -- Insert steps and collect edge info
        v_steps.DELETE;
        v_idx := 0;
        FOR s IN c_steps(wf.EXECUTION_STEPS) LOOP
            INSERT INTO WORKFLOW_STEPS (
                WORKFLOW_DEFINITION_ID, STEP_ID, STEP_ORDER, STEP_NAME, STEP_TYPE,
                REFERENCED_ACTION_ID, INTEGRATION_TYPE, OPERATION,
                INPUT_MAPPING, OUTPUT_MAPPING, CONDITION,
                RETRY_ENABLED, RETRY_MAX_ATTEMPTS, RETRY_INTERVAL_SECONDS,
                RETRY_BACKOFF_MULTIPLIER, JOIN_POLICY
            ) VALUES (
                v_wf_def_id,
                s.step_id,
                s.step_order,
                NVL(s.step_name, 'Step ' || s.step_order),
                s.step_type,
                s.referenced_action_id,
                s.integration_type,
                s.operation,
                CASE WHEN s.input_mapping IS NOT NULL AND DBMS_LOB.GETLENGTH(s.input_mapping) > 0
                     THEN s.input_mapping ELSE NULL END,
                CASE WHEN s.output_mapping IS NOT NULL AND DBMS_LOB.GETLENGTH(s.output_mapping) > 0
                     THEN s.output_mapping ELSE NULL END,
                CASE WHEN s.condition_expr IS NOT NULL AND DBMS_LOB.GETLENGTH(s.condition_expr) > 0
                     THEN s.condition_expr ELSE NULL END,
                NVL(s.retry_enabled, 0),
                s.retry_max_attempts,
                s.retry_interval_seconds,
                s.retry_backoff_multiplier,
                s.join_policy
            ) RETURNING ID INTO v_step_db_id;

            v_idx := v_idx + 1;
            v_steps(v_idx).step_id := s.step_id;
            v_steps(v_idx).on_success_step_ids := s.on_success_step_ids;
            v_steps(v_idx).on_error_step_ids := s.on_error_step_ids;
            v_steps(v_idx).db_id := v_step_db_id;
        END LOOP;

        -- Insert edges (success + error)
        FOR i IN 1..v_steps.COUNT LOOP
            -- Success edges
            IF v_steps(i).on_success_step_ids IS NOT NULL
               AND DBMS_LOB.GETLENGTH(v_steps(i).on_success_step_ids) > 2 THEN
                FOR e IN c_edge_targets(v_steps(i).on_success_step_ids) LOOP
                    -- Resolve target step_id to DB id
                    SELECT ID INTO v_to_step_db_id
                    FROM WORKFLOW_STEPS
                    WHERE WORKFLOW_DEFINITION_ID = v_wf_def_id
                      AND STEP_ID = e.target_step_id;

                    INSERT INTO WORKFLOW_STEP_EDGES (FROM_STEP_ID, TO_STEP_ID, EDGE_TYPE)
                    VALUES (v_steps(i).db_id, v_to_step_db_id, 'success');
                END LOOP;
            END IF;

            -- Error edges
            IF v_steps(i).on_error_step_ids IS NOT NULL
               AND DBMS_LOB.GETLENGTH(v_steps(i).on_error_step_ids) > 2 THEN
                FOR e IN c_edge_targets(v_steps(i).on_error_step_ids) LOOP
                    SELECT ID INTO v_to_step_db_id
                    FROM WORKFLOW_STEPS
                    WHERE WORKFLOW_DEFINITION_ID = v_wf_def_id
                      AND STEP_ID = e.target_step_id;

                    INSERT INTO WORKFLOW_STEP_EDGES (FROM_STEP_ID, TO_STEP_ID, EDGE_TYPE)
                    VALUES (v_steps(i).db_id, v_to_step_db_id, 'error');
                END LOOP;
            END IF;
        END LOOP;

        -- Batch commit every 100 workflows
        v_batch_count := v_batch_count + 1;
        IF MOD(v_batch_count, 100) = 0 THEN
            COMMIT;
        END IF;
    END LOOP;

    -- Final commit for remaining rows
    COMMIT;
END;
/
