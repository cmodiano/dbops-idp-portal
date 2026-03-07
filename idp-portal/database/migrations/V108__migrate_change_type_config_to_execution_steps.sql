-- Story 57.18 Task 1: Migrate actions with change_type_config but no execution_steps
-- Converts legacy change_type_config to execution_steps (3 steps: create-change -> execute-action -> close-change)
-- Reproduces the logic of _build_change_wrapper_steps() from container_workflow_runtime.py (Story 57.11)
--
-- Fix: IS_DELETED n'existe pas (schema uses DELETED_AT). Use DELETED_AT IS NULL.
-- Fix: Use explicit variables for loop to avoid PLS-00364 (r in nested SQL).
-- Fix: RETURNING CLOB not valid in PL/SQL expression context.
--      JSON_ARRAY default VARCHAR2(4000) suffices for 3 steps (~1-2KB).

DECLARE
    v_count NUMBER := 0;
    v_id    NUMBER;
    v_name  VARCHAR2(255);
    v_cfg   CLOB;
    v_steps CLOB;
BEGIN
    FOR rec IN (
        SELECT ID, NAME, CHANGE_TYPE_CONFIG
        FROM ACTIONS_CATALOG
        WHERE CHANGE_TYPE_CONFIG IS NOT NULL
          AND (EXECUTION_STEPS IS NULL OR DBMS_LOB.GETLENGTH(EXECUTION_STEPS) = 0)
          AND DELETED_AT IS NULL
    ) LOOP
        v_id   := rec.ID;
        v_name := rec.NAME;
        v_cfg  := rec.CHANGE_TYPE_CONFIG;

        v_steps := JSON_ARRAY(
                JSON_OBJECT(
                    'order'             VALUE 1,
                    'step_id'           VALUE 'create-change',
                    'step_type'         VALUE 'service_call',
                    'name'              VALUE 'Créer change ServiceNow',
                    'integration_type'  VALUE 'servicenow',
                    'operation'         VALUE 'create_change',
                    'input_mapping'     VALUE JSON_OBJECT(
                        'short_description' VALUE SUBSTR('IDP Portal — ' || v_name, 1, 160),
                        'change_type'       VALUE COALESCE(JSON_VALUE(v_cfg, '$.model'), 'standard'),
                        'category'          VALUE COALESCE(JSON_VALUE(v_cfg, '$.category'), ''),
                        'assignment_group'  VALUE COALESCE(JSON_VALUE(v_cfg, '$.assignment_group'), '')
                    ),
                    'output_mapping'    VALUE JSON_OBJECT(
                        'change_number' VALUE '$.number',
                        'sys_id'        VALUE '$.sys_id'
                    ),
                    'on_success_step_id' VALUE 'execute-action'
                ),
                JSON_OBJECT(
                    'order'                VALUE 2,
                    'step_id'              VALUE 'execute-action',
                    'step_type'            VALUE 'platform',
                    'name'                 VALUE v_name,
                    'referenced_action_id' VALUE v_id,
                    'on_success_step_id'   VALUE 'close-change'
                ),
                JSON_OBJECT(
                    'order'            VALUE 3,
                    'step_id'          VALUE 'close-change',
                    'step_type'        VALUE 'service_call',
                    'name'             VALUE 'Fermer change ServiceNow',
                    'integration_type' VALUE 'servicenow',
                    'operation'        VALUE 'close_change',
                    'input_mapping'    VALUE JSON_OBJECT(
                        'change_id'  VALUE '{{ steps[''create-change''][''change_number''] }}',
                        'close_code' VALUE 'successful'
                    ),
                    'output_mapping'   VALUE JSON_OBJECT(
                        'closed' VALUE '$.closed'
                    )
                )
            );

        UPDATE ACTIONS_CATALOG
        SET EXECUTION_STEPS = v_steps,
            ITEM_TYPE = 'workflow'
        WHERE ID = v_id;

        v_count := v_count + 1;
    END LOOP;

    DBMS_OUTPUT.PUT_LINE('Migrated ' || v_count || ' actions from change_type_config to execution_steps');
END;
/
