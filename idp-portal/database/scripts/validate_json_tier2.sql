-- validate_json_tier2.sql
-- Script de validation prealable - Story 78.13
-- Verifier que toutes les valeurs non-NULL dans les colonnes JSON Tier 2
-- sont du JSON valide AVANT d'appliquer la migration V134.
--
-- Usage : executer manuellement en pre-production avant V134.
-- Si des lignes non-JSON sont detectees, corriger les donnees avant migration.

SET SERVEROUTPUT ON
SET LINESIZE 200
SET PAGESIZE 1000
SET TIMING ON

DECLARE
    v_count    NUMBER;
    v_total    NUMBER := 0;
    v_errors   NUMBER := 0;

    TYPE t_col_rec IS RECORD (
        table_name  VARCHAR2(128),
        column_name VARCHAR2(128),
        pk_column   VARCHAR2(128)
    );
    TYPE t_col_tab IS TABLE OF t_col_rec INDEX BY PLS_INTEGER;
    v_cols t_col_tab;

    v_pk       NUMBER;
    v_substr   VARCHAR2(200);
    v_col_len  NUMBER;

    TYPE t_ref_cursor IS REF CURSOR;
    v_cursor   t_ref_cursor;
BEGIN
    -- Define all 16 target columns with their PK columns
    v_cols(1).table_name := 'EXECUTIONS';           v_cols(1).column_name := 'PARAMETERS';           v_cols(1).pk_column := 'ID';
    v_cols(2).table_name := 'EXECUTION_STEPS';      v_cols(2).column_name := 'OUTPUT';               v_cols(2).pk_column := 'ID';
    v_cols(3).table_name := 'EXECUTION_TARGETS';    v_cols(3).column_name := 'TARGET_METADATA';      v_cols(3).pk_column := 'ID';
    v_cols(4).table_name := 'INTEGRATIONS';         v_cols(4).column_name := 'CONFIG';               v_cols(4).pk_column := 'ID';
    v_cols(5).table_name := 'SCHEDULED_EXECUTIONS'; v_cols(5).column_name := 'PARAMETERS';           v_cols(5).pk_column := 'ID';
    v_cols(6).table_name := 'RECURRING_PATTERNS';   v_cols(6).column_name := 'PATTERN_CONFIG';       v_cols(6).pk_column := 'ID';
    v_cols(7).table_name := 'INTEGRATION_ACTIONS';  v_cols(7).column_name := 'REQUIRED_PARAMS';      v_cols(7).pk_column := 'ID';
    v_cols(8).table_name := 'INTEGRATION_ACTIONS';  v_cols(8).column_name := 'OPTIONAL_PARAMS';      v_cols(8).pk_column := 'ID';
    v_cols(9).table_name := 'INTEGRATION_ACTIONS';  v_cols(9).column_name := 'RESPONSE_FORMAT';      v_cols(9).pk_column := 'ID';
    v_cols(10).table_name := 'ACTIONS_CATALOG';     v_cols(10).column_name := 'PARAMETERS_SCHEMA';   v_cols(10).pk_column := 'ID';
    v_cols(11).table_name := 'ACTIONS_CATALOG';     v_cols(11).column_name := 'IMPACT_RULES';        v_cols(11).pk_column := 'ID';
    v_cols(12).table_name := 'ACTIONS_CATALOG';     v_cols(12).column_name := 'EXECUTION_STEPS';     v_cols(12).pk_column := 'ID';
    v_cols(13).table_name := 'ACTIONS_CATALOG';     v_cols(13).column_name := 'REMEDIATION_RULES';   v_cols(13).pk_column := 'ID';
    v_cols(14).table_name := 'ACTIONS_CATALOG';     v_cols(14).column_name := 'BUSINESS_RULE_POLICIES'; v_cols(14).pk_column := 'ID';
    v_cols(15).table_name := 'BUSINESS_RULE_POLICIES'; v_cols(15).column_name := 'POLICY_JSON';      v_cols(15).pk_column := 'ID';
    v_cols(16).table_name := 'WORKFLOW_COMMANDS';   v_cols(16).column_name := 'PAYLOAD';             v_cols(16).pk_column := 'ID';

    DBMS_OUTPUT.PUT_LINE('==========================================================');
    DBMS_OUTPUT.PUT_LINE('  Validation JSON Tier 2 - Pre-migration V134');
    DBMS_OUTPUT.PUT_LINE('  Date : ' || TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS'));
    DBMS_OUTPUT.PUT_LINE('==========================================================');
    DBMS_OUTPUT.PUT_LINE('');

    FOR i IN 1..v_cols.COUNT LOOP
        EXECUTE IMMEDIATE
            'SELECT COUNT(*) FROM ' || v_cols(i).table_name ||
            ' WHERE ' || v_cols(i).column_name || ' IS NOT NULL' ||
            ' AND ' || v_cols(i).column_name || ' IS NOT JSON'
        INTO v_count;

        v_total := v_total + 1;

        IF v_count = 0 THEN
            DBMS_OUTPUT.PUT_LINE('OK    ' || RPAD(v_cols(i).table_name, 30) || '.' ||
                RPAD(v_cols(i).column_name, 25) || ' : 0 lignes non-JSON');
        ELSE
            v_errors := v_errors + v_count;
            DBMS_OUTPUT.PUT_LINE('FAIL  ' || RPAD(v_cols(i).table_name, 30) || '.' ||
                RPAD(v_cols(i).column_name, 25) || ' : ' || v_count || ' lignes non-JSON');

            -- Show up to 5 offending rows with PK and content excerpt
            OPEN v_cursor FOR
                'SELECT ' || v_cols(i).pk_column ||
                ', SUBSTR(' || v_cols(i).column_name || ', 1, 100)' ||
                ', DBMS_LOB.GETLENGTH(' || v_cols(i).column_name || ')' ||
                ' FROM ' || v_cols(i).table_name ||
                ' WHERE ' || v_cols(i).column_name || ' IS NOT NULL' ||
                ' AND ' || v_cols(i).column_name || ' IS NOT JSON' ||
                ' AND ROWNUM <= 5';
            LOOP
                FETCH v_cursor INTO v_pk, v_substr, v_col_len;
                EXIT WHEN v_cursor%NOTFOUND;
                IF v_col_len > 100 THEN
                    DBMS_OUTPUT.PUT_LINE('       -> PK=' || v_pk || '  contenu (' || v_col_len || ' chars): ' || v_substr || '...');
                ELSE
                    DBMS_OUTPUT.PUT_LINE('       -> PK=' || v_pk || '  contenu: ' || v_substr);
                END IF;
            END LOOP;
            CLOSE v_cursor;
        END IF;
    END LOOP;

    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('==========================================================');
    DBMS_OUTPUT.PUT_LINE('  RESULTAT : ' || v_total || ' colonnes verifiees');
    IF v_errors = 0 THEN
        DBMS_OUTPUT.PUT_LINE('  STATUS  : OK - Aucune donnee non-JSON detectee');
        DBMS_OUTPUT.PUT_LINE('  ACTION  : Migration V134 peut etre appliquee en toute securite');
    ELSE
        DBMS_OUTPUT.PUT_LINE('  STATUS  : ECHEC - ' || v_errors || ' lignes non-JSON detectees');
        DBMS_OUTPUT.PUT_LINE('  ACTION  : Corriger les donnees avant d''appliquer V134');
    END IF;
    DBMS_OUTPUT.PUT_LINE('==========================================================');
END;
/
