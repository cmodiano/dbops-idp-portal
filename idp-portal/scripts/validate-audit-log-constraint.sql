-- validate-audit-log-constraint.sql
-- Story 9.8: Script de validation de la contrainte CHECK CK_AUDIT_LOG_ACTION_TYPE
--
-- Usage:
--   sqlplus idp_app/Oracle123!@localhost:1521/FREEPDB1 @scripts/validate-audit-log-constraint.sql
--
-- Ce script vérifie que tous les action types attendus sont présents dans la contrainte CHECK.
-- Il échoue avec RAISE_APPLICATION_ERROR si des types sont manquants.

SET SERVEROUTPUT ON
SET LINESIZE 200

PROMPT
PROMPT ========================================
PROMPT Validation contrainte CK_AUDIT_LOG_ACTION_TYPE
PROMPT ========================================
PROMPT

DECLARE
    v_constraint_text CLOB;
    v_missing_types VARCHAR2(4000) := '';
    v_found_count NUMBER := 0;
    v_expected_count NUMBER := 0;

    -- Liste des types à vérifier
    TYPE t_action_types IS TABLE OF VARCHAR2(50);
    v_action_types t_action_types := t_action_types(
        -- Action lifecycle (V004)
        'ACTION_CREATED',
        'ACTION_UPDATED',
        'ACTION_PUBLISHED',
        'ACTION_DISABLED',
        'ACTION_ENABLED',
        -- Execution lifecycle (V028)
        'EXECUTION_SUBMITTED',
        'EXECUTION_STARTED',
        'EXECUTION_COMPLETED',
        'EXECUTION_FAILED',
        -- ServiceNow change (V028)
        'SERVICENOW_CHANGE_CREATED',
        -- Approval workflow (V032 - Story 7.4)
        'EXECUTION_PENDING_APPROVAL',
        'EXECUTION_APPROVED',
        'EXECUTION_REJECTED',
        -- Remediation (V034 - Story 9.2)
        'REMEDIATION_EXECUTION_CREATED',
        -- Auto-remediation (V035 - Story 9.3)
        'AUTO_REMEDIATION_TRIGGERED',
        'AUTO_REMEDIATION_SUCCESS',
        'AUTO_REMEDIATION_FAILED'
    );

BEGIN
    -- Récupérer le texte de la contrainte
    BEGIN
        SELECT SEARCH_CONDITION INTO v_constraint_text
        FROM USER_CONSTRAINTS
        WHERE CONSTRAINT_NAME = 'CK_AUDIT_LOG_ACTION_TYPE';
    EXCEPTION
        WHEN NO_DATA_FOUND THEN
            RAISE_APPLICATION_ERROR(-20001,
                'ERREUR CRITIQUE: Contrainte CK_AUDIT_LOG_ACTION_TYPE introuvable! ' ||
                'Vérifier que les migrations Flyway ont été appliquées.');
    END;

    DBMS_OUTPUT.PUT_LINE('Contrainte trouvée. Vérification des action types...');
    DBMS_OUTPUT.PUT_LINE('');

    v_expected_count := v_action_types.COUNT;

    -- Vérifier chaque type
    FOR i IN 1..v_action_types.COUNT LOOP
        IF INSTR(v_constraint_text, v_action_types(i)) > 0 THEN
            DBMS_OUTPUT.PUT_LINE('  ✓ ' || v_action_types(i));
            v_found_count := v_found_count + 1;
        ELSE
            DBMS_OUTPUT.PUT_LINE('  ✗ ' || v_action_types(i) || ' (MANQUANT!)');
            v_missing_types := v_missing_types || v_action_types(i) || ', ';
        END IF;
    END LOOP;

    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('========================================');

    IF v_missing_types IS NOT NULL AND LENGTH(v_missing_types) > 0 THEN
        -- Retirer la virgule finale
        v_missing_types := RTRIM(v_missing_types, ', ');

        DBMS_OUTPUT.PUT_LINE('ÉCHEC: ' || v_found_count || '/' || v_expected_count || ' types trouvés');
        DBMS_OUTPUT.PUT_LINE('');
        DBMS_OUTPUT.PUT_LINE('Types manquants: ' || v_missing_types);
        DBMS_OUTPUT.PUT_LINE('');
        DBMS_OUTPUT.PUT_LINE('Action requise:');
        DBMS_OUTPUT.PUT_LINE('  1. Identifier la migration qui a perdu ces types');
        DBMS_OUTPUT.PUT_LINE('  2. Créer une migration corrective ou ré-appliquer les migrations');
        DBMS_OUTPUT.PUT_LINE('  3. Relancer ce script pour valider');

        RAISE_APPLICATION_ERROR(-20002,
            'Contrainte CHECK incomplète. Types manquants: ' || v_missing_types);
    ELSE
        DBMS_OUTPUT.PUT_LINE('SUCCÈS: ' || v_found_count || '/' || v_expected_count || ' types trouvés');
        DBMS_OUTPUT.PUT_LINE('');
        DBMS_OUTPUT.PUT_LINE('La contrainte CK_AUDIT_LOG_ACTION_TYPE est à jour.');
        DBMS_OUTPUT.PUT_LINE('Tous les action types attendus sont présents.');
    END IF;

    DBMS_OUTPUT.PUT_LINE('========================================');
END;
/

-- Afficher aussi le contenu brut de la contrainte pour référence
PROMPT
PROMPT Contenu brut de la contrainte:
PROMPT -----------------------------
SELECT SEARCH_CONDITION
FROM USER_CONSTRAINTS
WHERE CONSTRAINT_NAME = 'CK_AUDIT_LOG_ACTION_TYPE';

-- Afficher les dernières migrations Flyway
PROMPT
PROMPT Dernières migrations Flyway appliquées:
PROMPT --------------------------------------
SELECT installed_rank, version, description,
       TO_CHAR(installed_on, 'YYYY-MM-DD HH24:MI:SS') AS installed_on,
       CASE WHEN success = 1 THEN 'OK' ELSE 'FAIL' END AS status
FROM flyway_schema_history
ORDER BY installed_rank DESC
FETCH FIRST 10 ROWS ONLY;

EXIT;
