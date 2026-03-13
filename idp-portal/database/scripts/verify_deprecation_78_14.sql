-- verify_deprecation_78_14.sql
-- Script de verification post-migration - Story 78.14
-- Confirmer que:
--   1. Les COMMENT ON COLUMN DEPRECATED sont en place (3 colonnes)
--   2. Le CHECK constraint CHK_EXECUTION_STATUS ne contient plus PENDING_APPROVAL
--   3. Aucune ligne n'a STATUS = 'PENDING_APPROVAL'
--
-- Usage : executer apres la migration V135 pour valider le resultat.

SET SERVEROUTPUT ON
SET LINESIZE 200
SET PAGESIZE 100

-- 1. Verifier les COMMENT ON COLUMN (3 colonnes avec mot-cle DEPRECATED)
PROMPT
PROMPT === 1. COMMENT ON COLUMN — colonnes deprecated ===
SELECT
    COLUMN_NAME,
    COMMENTS
FROM ALL_COL_COMMENTS
WHERE TABLE_NAME = 'EXECUTIONS'
  AND COLUMN_NAME IN ('APPROVED_BY', 'APPROVED_AT', 'APPROVAL_COMMENT')
ORDER BY COLUMN_NAME;

DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count
    FROM ALL_COL_COMMENTS
    WHERE TABLE_NAME = 'EXECUTIONS'
      AND COLUMN_NAME IN ('APPROVED_BY', 'APPROVED_AT', 'APPROVAL_COMMENT')
      AND COMMENTS LIKE '%DEPRECATED%';

    IF v_count = 3 THEN
        DBMS_OUTPUT.PUT_LINE('OK: 3/3 colonnes ont le commentaire DEPRECATED');
    ELSE
        DBMS_OUTPUT.PUT_LINE('ERREUR: ' || v_count || '/3 colonnes ont le commentaire DEPRECATED');
    END IF;
END;
/

-- 2. Verifier le CHECK constraint CHK_EXECUTION_STATUS
PROMPT
PROMPT === 2. CHECK constraint CHK_EXECUTION_STATUS ===
SELECT
    CONSTRAINT_NAME,
    STATUS,
    SEARCH_CONDITION
FROM USER_CONSTRAINTS
WHERE CONSTRAINT_NAME = 'CHK_EXECUTION_STATUS'
  AND TABLE_NAME = 'EXECUTIONS';

DECLARE
    v_condition LONG;
    v_count     NUMBER;
BEGIN
    SELECT SEARCH_CONDITION INTO v_condition
    FROM USER_CONSTRAINTS
    WHERE CONSTRAINT_NAME = 'CHK_EXECUTION_STATUS'
      AND TABLE_NAME = 'EXECUTIONS';

    IF INSTR(UPPER(v_condition), 'PENDING_APPROVAL') > 0 THEN
        DBMS_OUTPUT.PUT_LINE('ERREUR: CHK_EXECUTION_STATUS contient encore PENDING_APPROVAL');
    ELSE
        DBMS_OUTPUT.PUT_LINE('OK: CHK_EXECUTION_STATUS ne contient plus PENDING_APPROVAL');
    END IF;

    -- Verifier que les 7 statuts attendus sont presents
    SELECT COUNT(*) INTO v_count FROM (
        SELECT 'SUBMITTED' AS s FROM DUAL UNION ALL
        SELECT 'INTEGRATION_ERROR' FROM DUAL UNION ALL
        SELECT 'RUNNING' FROM DUAL UNION ALL
        SELECT 'COMPLETED' FROM DUAL UNION ALL
        SELECT 'FAILED' FROM DUAL UNION ALL
        SELECT 'CANCELLED' FROM DUAL UNION ALL
        SELECT 'REJECTED' FROM DUAL
    ) expected
    WHERE INSTR(UPPER(v_condition), expected.s) > 0;

    DBMS_OUTPUT.PUT_LINE('Statuts presents dans constraint: ' || v_count || '/7');
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        DBMS_OUTPUT.PUT_LINE('ERREUR: Constraint CHK_EXECUTION_STATUS introuvable');
END;
/

-- 3. Verifier qu'aucune ligne n'a STATUS = 'PENDING_APPROVAL'
PROMPT
PROMPT === 3. Lignes PENDING_APPROVAL residuelles ===
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM EXECUTIONS WHERE STATUS = 'PENDING_APPROVAL';
    IF v_count = 0 THEN
        DBMS_OUTPUT.PUT_LINE('OK: Aucune ligne avec STATUS = PENDING_APPROVAL');
    ELSE
        DBMS_OUTPUT.PUT_LINE('ERREUR: ' || v_count || ' lignes avec STATUS = PENDING_APPROVAL');
    END IF;
END;
/

PROMPT
PROMPT === Verification 78.14 terminee ===
