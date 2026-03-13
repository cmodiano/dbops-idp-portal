-- verify_json_constraints_tier2.sql
-- Script de verification post-migration - Story 78.13
-- Confirmer que les 16 contraintes IS JSON Tier 2 sont presentes et activees.
--
-- Usage : executer apres la migration V134 pour valider le resultat.
-- Resultat attendu : 16 contraintes CHECK avec status ENABLED.

SET SERVEROUTPUT ON
SET LINESIZE 200
SET PAGESIZE 100

-- List all expected constraints and their actual status
SELECT
    CONSTRAINT_NAME,
    TABLE_NAME,
    STATUS,
    VALIDATED
FROM USER_CONSTRAINTS
WHERE CONSTRAINT_NAME IN (
    'CK_EXEC_PARAMETERS_JSON',
    'CK_EXECSTEP_OUTPUT_JSON',
    'CK_EXECTGT_TARGET_METADATA_JSON',
    'CK_INTEG_CONFIG_JSON',
    'CK_SCHEDEXEC_PARAMETERS_JSON',
    'CK_RECPAT_PATTERN_CONFIG_JSON',
    'CK_INTACT_REQUIRED_PARAMS_JSON',
    'CK_INTACT_OPTIONAL_PARAMS_JSON',
    'CK_INTACT_RESPONSE_FORMAT_JSON',
    'CK_ACTCAT_PARAMETERS_SCHEMA_JSON',
    'CK_ACTCAT_IMPACT_RULES_JSON',
    'CK_ACTCAT_EXECUTION_STEPS_JSON',
    'CK_ACTCAT_REMEDIATION_RULES_JSON',
    'CK_ACTCAT_BIZ_RULE_POLICIES_JSON',
    'CK_BRP_POLICY_JSON_JSON',
    'CK_WFCMD_PAYLOAD_JSON'
)
ORDER BY TABLE_NAME, CONSTRAINT_NAME;

-- Summary count (uses same list as above)
DECLARE
    v_total    NUMBER;
    v_enabled  NUMBER;
BEGIN
    SELECT COUNT(*), COUNT(CASE WHEN STATUS = 'ENABLED' THEN 1 END)
    INTO v_total, v_enabled
    FROM USER_CONSTRAINTS
    WHERE CONSTRAINT_NAME IN (
        'CK_EXEC_PARAMETERS_JSON',
        'CK_EXECSTEP_OUTPUT_JSON',
        'CK_EXECTGT_TARGET_METADATA_JSON',
        'CK_INTEG_CONFIG_JSON',
        'CK_SCHEDEXEC_PARAMETERS_JSON',
        'CK_RECPAT_PATTERN_CONFIG_JSON',
        'CK_INTACT_REQUIRED_PARAMS_JSON',
        'CK_INTACT_OPTIONAL_PARAMS_JSON',
        'CK_INTACT_RESPONSE_FORMAT_JSON',
        'CK_ACTCAT_PARAMETERS_SCHEMA_JSON',
        'CK_ACTCAT_IMPACT_RULES_JSON',
        'CK_ACTCAT_EXECUTION_STEPS_JSON',
        'CK_ACTCAT_REMEDIATION_RULES_JSON',
        'CK_ACTCAT_BIZ_RULE_POLICIES_JSON',
        'CK_BRP_POLICY_JSON_JSON',
        'CK_WFCMD_PAYLOAD_JSON'
    );

    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('==========================================================');
    DBMS_OUTPUT.PUT_LINE('  Verification contraintes JSON Tier 2 - Post-migration V134');
    DBMS_OUTPUT.PUT_LINE('==========================================================');
    DBMS_OUTPUT.PUT_LINE('  Contraintes trouvees  : ' || v_total || ' / 16');
    DBMS_OUTPUT.PUT_LINE('  Contraintes ENABLED   : ' || v_enabled || ' / 16');

    IF v_enabled = 16 THEN
        DBMS_OUTPUT.PUT_LINE('  STATUS : OK - Toutes les contraintes sont en place et activees');
    ELSIF v_total = 16 AND v_enabled < 16 THEN
        DBMS_OUTPUT.PUT_LINE('  STATUS : ATTENTION - ' || (16 - v_enabled) || ' contraintes trouvees mais desactivees');
    ELSE
        DBMS_OUTPUT.PUT_LINE('  STATUS : ECHEC - ' || (16 - v_total) || ' contraintes manquantes');
    END IF;
    DBMS_OUTPUT.PUT_LINE('==========================================================');
END;
/
