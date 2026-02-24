-- V087 ROLLBACK : Supprimer PKG_IDP_MAINTENANCE et IDP_MAINTENANCE_LOG
-- Story 40.5 - Epic 40: Partitionnement et rétention tables performance
--
-- USAGE DBA MANUEL UNIQUEMENT — Ce script n'est PAS exécuté par Flyway.
-- À utiliser pour annuler l'installation de V087__create_purge_procedure.sql.
--
-- PRÉREQUIS :
--   1. Vérifier qu'aucune exécution de PKG_IDP_MAINTENANCE n'est en cours
--   2. Vérifier qu'aucun JOB DBMS_SCHEDULER ne référence PKG_IDP_MAINTENANCE
--   3. Effectuer un export des données IDP_MAINTENANCE_LOG si historique nécessaire
--
-- DIAGNOSTIC PRÉLIMINAIRE :
--   -- Vérifier l'existence des objets
--   SELECT OBJECT_NAME, OBJECT_TYPE, STATUS
--   FROM USER_OBJECTS
--   WHERE OBJECT_NAME IN ('PKG_IDP_MAINTENANCE', 'IDP_MAINTENANCE_LOG')
--   ORDER BY OBJECT_TYPE;
--
--   -- Vérifier les jobs DBMS_SCHEDULER qui référencent le package
--   SELECT JOB_NAME, JOB_ACTION, STATE
--   FROM USER_SCHEDULER_JOBS
--   WHERE JOB_ACTION LIKE '%PKG_IDP_MAINTENANCE%';

-- ===========================================================================
-- ÉTAPE 1 : Désactiver et supprimer le job DBMS_SCHEDULER (si créé)
-- ===========================================================================
-- À exécuter uniquement si JOB_IDP_MAINTENANCE_PURGE a été créé manuellement (§7 du guide).
-- Commenter ou ignorer si le job n'existe pas.
BEGIN
    DBMS_SCHEDULER.DROP_JOB(job_name => 'JOB_IDP_MAINTENANCE_PURGE', force => TRUE);
    DBMS_OUTPUT.PUT_LINE('JOB_IDP_MAINTENANCE_PURGE supprimé.');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -27475 THEN
            -- ORA-27475: job inexistant — normal si jamais créé
            DBMS_OUTPUT.PUT_LINE('JOB_IDP_MAINTENANCE_PURGE inexistant, ignoré.');
        ELSE
            RAISE;
        END IF;
END;
/

-- ===========================================================================
-- ÉTAPE 2 : Supprimer le package PKG_IDP_MAINTENANCE
-- (supprime à la fois la spec et le body)
-- ===========================================================================
BEGIN
    EXECUTE IMMEDIATE 'DROP PACKAGE PKG_IDP_MAINTENANCE';
    DBMS_OUTPUT.PUT_LINE('PKG_IDP_MAINTENANCE supprimé.');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -4043 THEN
            -- ORA-04043: object PKG_IDP_MAINTENANCE does not exist
            DBMS_OUTPUT.PUT_LINE('PKG_IDP_MAINTENANCE inexistant, ignoré.');
        ELSE
            RAISE;
        END IF;
END;
/

-- ===========================================================================
-- ÉTAPE 3 : Supprimer la table IDP_MAINTENANCE_LOG
-- PURGE : suppression physique sans passer par la Recycle Bin
-- ===========================================================================
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE IDP_MAINTENANCE_LOG PURGE';
    DBMS_OUTPUT.PUT_LINE('IDP_MAINTENANCE_LOG supprimée (PURGE).');
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -942 THEN
            -- ORA-00942: table or view does not exist
            DBMS_OUTPUT.PUT_LINE('IDP_MAINTENANCE_LOG inexistante, ignoré.');
        ELSE
            RAISE;
        END IF;
END;
/

-- ===========================================================================
-- ÉTAPE 4 : Valider la suppression
-- ===========================================================================
DECLARE
    v_pkg_count   NUMBER;
    v_table_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_pkg_count
    FROM USER_OBJECTS
    WHERE OBJECT_NAME = 'PKG_IDP_MAINTENANCE';

    SELECT COUNT(*) INTO v_table_count
    FROM USER_TABLES
    WHERE TABLE_NAME = 'IDP_MAINTENANCE_LOG';

    IF v_pkg_count > 0 THEN
        DBMS_OUTPUT.PUT_LINE('WARNING: PKG_IDP_MAINTENANCE still exists (' || v_pkg_count || ' objects).');
    ELSE
        DBMS_OUTPUT.PUT_LINE('OK: PKG_IDP_MAINTENANCE absent.');
    END IF;

    IF v_table_count > 0 THEN
        DBMS_OUTPUT.PUT_LINE('WARNING: IDP_MAINTENANCE_LOG still exists.');
    ELSE
        DBMS_OUTPUT.PUT_LINE('OK: IDP_MAINTENANCE_LOG absent.');
    END IF;

    DBMS_OUTPUT.PUT_LINE('V087 rollback completed.');
END;
/

-- ===========================================================================
-- FLYWAY : Marquer V087 comme annulée dans flyway_schema_history
-- ===========================================================================
-- Après exécution du rollback, supprimer l'entrée V087 de Flyway pour permettre
-- une ré-exécution ou un saut de version :
--
-- DELETE FROM flyway_schema_history WHERE version = '087';
-- COMMIT;
--
-- Si vous souhaitez sauter définitivement V087 (sans re-exécuter) :
-- INSERT INTO flyway_schema_history (installed_rank, version, description, type, script,
--     checksum, installed_by, installed_on, execution_time, success)
-- VALUES (
--     (SELECT NVL(MAX(installed_rank),0)+1 FROM flyway_schema_history),
--     '087',
--     'create_purge_procedure - ROLLED BACK',
--     'SQL',
--     'V087__create_purge_procedure.sql',
--     0,
--     USER,
--     SYSDATE,
--     0,
--     1
-- );
-- COMMIT;
