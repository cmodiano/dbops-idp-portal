-- V086 ROLLBACK : Restaurer AUDIT_LOG non-partitionnée
-- Story 40.4 - Epic 40: Partitionnement et rétention tables performance
--
-- USAGE DBA MANUEL UNIQUEMENT — Ce script n'est PAS exécuté par Flyway.
-- À utiliser en cas de problème après exécution de V086__partition_audit_log.sql.
--
-- PRÉREQUIS :
--   1. Identifier le scénario applicable (voir ci-dessous)
--   2. Effectuer un backup avant exécution
--   3. Planifier une fenêtre de maintenance (durée estimée : 4-6h selon volume)
--   4. Valider sur DEV/PREPROD avant application PROD
--
-- DIAGNOSTIC PRÉLIMINAIRE :
--   SELECT TABLE_NAME FROM USER_TABLES
--   WHERE TABLE_NAME IN ('AUDIT_LOG', 'AUDIT_LOG_NEW', 'AUDIT_LOG_OLD');
--
-- SCÉNARIOS DE ROLLBACK :
--   Scénario A : V086 a échoué avant la Phase 4 (AUDIT_LOG_OLD n'existe pas)
--     → AUDIT_LOG originale encore intacte, AUDIT_LOG_NEW à supprimer
--     → Exécuter : Section A ci-dessous
--
--   Scénario B : V086 a échoué pendant/après Phase 4 (AUDIT_LOG_OLD existe)
--     → AUDIT_LOG_OLD existe, AUDIT_LOG est la version partitionnée (potentiellement incomplète)
--     → Exécuter : Section B ci-dessous (rollback complet)
--
--   Scénario C : V086 s'est terminée avec succès (AUDIT_LOG_OLD a été supprimée)
--     → Rollback doit recréer la table non-partitionnée depuis AUDIT_LOG partitionnée
--     → Exécuter : Section C ci-dessous (rollback post-succès)
--

-- ===========================================================================
-- SECTION A : Nettoyage si échec avant Phase 4 (AUDIT_LOG intacte)
-- ===========================================================================
-- Applicable si AUDIT_LOG existe ET AUDIT_LOG_OLD n'existe pas.
-- AUDIT_LOG originale est intacte avec son trigger TRG_AUDIT_LOG_IMMUTABLE.

/*
-- Supprimer AUDIT_LOG_NEW si elle existe (création partielle ou données incomplètes)
-- Handler ORA-00942 : si Phase 2 n'a pas été atteinte, AUDIT_LOG_NEW n'existe pas
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE AUDIT_LOG_NEW PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN RAISE; END IF;  -- ORA-00942: table ou vue inexistante
END;
/

-- Supprimer la table de contrôle si elle existe
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE AUDIT_LOG_MIGRATION_CHECK PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN RAISE; END IF;  -- ORA-00942: table ou vue inexistante
END;
/

-- AUDIT_LOG originale est intacte (avec TRG_AUDIT_LOG_IMMUTABLE), aucune autre action requise.
-- Flyway doit être réinitialisé pour permettre une ré-exécution de V086 corrigée :
--   DELETE FROM flyway_schema_history WHERE version = '086';
--   COMMIT;
*/

-- ===========================================================================
-- SECTION B : Rollback complet depuis AUDIT_LOG_OLD (échec mid-migration)
-- ===========================================================================
-- Applicable si AUDIT_LOG_OLD existe (Phase 4 a été exécutée mais V086 a échoué ensuite).
-- AUDIT_LOG est la version partitionnée (potentiellement incomplète).
-- NOTE : Le trigger TRG_AUDIT_LOG_IMMUTABLE est attaché à AUDIT_LOG_OLD — il sera restauré
--        avec le renommage AUDIT_LOG_OLD → AUDIT_LOG.

/*
-- Étape B.1 : Supprimer la version partitionnée (AUDIT_LOG = anciennement AUDIT_LOG_NEW)
-- AUDIT_LOG n'a aucune FK entrante — DROP direct sans DISABLE/ENABLE de contraintes externes
DROP TABLE AUDIT_LOG PURGE;

-- Étape B.2 : Renommer AUDIT_LOG_OLD → AUDIT_LOG
-- Le trigger TRG_AUDIT_LOG_IMMUTABLE revient avec la table
ALTER TABLE AUDIT_LOG_OLD RENAME TO AUDIT_LOG;

-- Étape B.3 : Supprimer la table de contrôle si elle existe
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE AUDIT_LOG_MIGRATION_CHECK PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN RAISE; END IF;
END;
/

-- Étape B.4 : Valider
SELECT COUNT(*) AS AUDIT_LOG_COUNT FROM AUDIT_LOG;
SELECT PARTITIONED FROM USER_TABLES WHERE TABLE_NAME = 'AUDIT_LOG';
-- PARTITIONED doit être 'NO'
SELECT TRIGGER_NAME, STATUS FROM USER_TRIGGERS WHERE TABLE_NAME = 'AUDIT_LOG';
-- TRG_AUDIT_LOG_IMMUTABLE doit être ENABLED
*/

-- ===========================================================================
-- SECTION C : Rollback post-succès (AUDIT_LOG_OLD supprimée)
-- ===========================================================================
-- Applicable si V086 s'est terminée avec succès et que AUDIT_LOG_OLD n'existe plus.
-- Cette section recrée une table non-partitionnée depuis la table partitionnée actuelle.
-- ATTENTION : Opération longue selon volume (estimation : 4-6h pour volumes PROD).
-- NOTE : Le trigger TRG_AUDIT_LOG_IMMUTABLE doit être recréé explicitement
--        (V086 Phase 9 l'a créé sur la table partitionnée ; après renommage il sera
--         attaché à AUDIT_LOG non-partitionnée).

/*
-- Étape C.0 : Vérification
DECLARE
    v_partitioned VARCHAR2(3);
BEGIN
    SELECT PARTITIONED INTO v_partitioned FROM USER_TABLES WHERE TABLE_NAME = 'AUDIT_LOG';
    IF v_partitioned != 'YES' THEN
        RAISE_APPLICATION_ERROR(-20010, 'AUDIT_LOG n''est pas partitionnée - rollback inutile');
    END IF;
    DBMS_OUTPUT.PUT_LINE('AUDIT_LOG est bien partitionnée (Range INTERVAL) - rollback applicable');
END;
/

-- Étape C.1 : Capturer COUNT de référence
CREATE TABLE AUDIT_LOG_ROLLBACK_CHECK AS
    SELECT COUNT(*) AS ROW_COUNT FROM AUDIT_LOG;

-- Étape C.2 : Créer la table non-partitionnée de destination
-- Colonnes conformes à l'état post-V028 (CORRELATION_ID ajouté)
-- NOTE: GENERATED BY DEFAULT ON NULL (V086 a migré de GENERATED ALWAYS)
CREATE TABLE AUDIT_LOG_NOPART (
    ID              NUMBER GENERATED BY DEFAULT ON NULL AS IDENTITY,
    TIMESTAMP       TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    USER_ID         VARCHAR2(100) NOT NULL,
    ACTION_TYPE     VARCHAR2(50) NOT NULL,
    ENTITY_TYPE     VARCHAR2(50) NOT NULL,
    ENTITY_ID       NUMBER NOT NULL,
    DETAILS         CLOB,
    IP_ADDRESS      VARCHAR2(45),
    CORRELATION_ID  VARCHAR2(64),
    CONSTRAINT PK_AUDIT_LOG_NOPART PRIMARY KEY (ID)
);

-- Étape C.3 : Copier les données
INSERT /*+ APPEND PARALLEL(4) */ INTO AUDIT_LOG_NOPART
    (ID, TIMESTAMP, USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
     DETAILS, IP_ADDRESS, CORRELATION_ID)
SELECT
     ID, TIMESTAMP, USER_ID, ACTION_TYPE, ENTITY_TYPE, ENTITY_ID,
     DETAILS, IP_ADDRESS, CORRELATION_ID
FROM AUDIT_LOG;
COMMIT;

-- Étape C.4 : Recaler la séquence IDENTITY
DECLARE
    v_max NUMBER;
BEGIN
    SELECT NVL(MAX(ID), 0) INTO v_max FROM AUDIT_LOG_NOPART;
    IF v_max > 0 THEN
        EXECUTE IMMEDIATE
            'ALTER TABLE AUDIT_LOG_NOPART MODIFY ID GENERATED BY DEFAULT ON NULL AS IDENTITY (START WITH '
            || (v_max + 1) || ' INCREMENT BY 1 NOCACHE)';
    END IF;
END;
/

-- Étape C.5 : Valider COUNT avant renommage
DECLARE
    v_orig NUMBER;
    v_new  NUMBER;
BEGIN
    SELECT ROW_COUNT INTO v_orig FROM AUDIT_LOG_ROLLBACK_CHECK;
    SELECT COUNT(*) INTO v_new FROM AUDIT_LOG_NOPART;
    IF v_new != v_orig THEN
        RAISE_APPLICATION_ERROR(-20011,
            'ROLLBACK COUNT MISMATCH: original=' || v_orig || ', restored=' || v_new);
    END IF;
    DBMS_OUTPUT.PUT_LINE('Rollback count validated: ' || v_new || ' rows');
END;
/

-- Étape C.6 : Supprimer la version partitionnée
-- AUDIT_LOG n'a aucune FK entrante — DROP direct
DROP TABLE AUDIT_LOG PURGE;

-- Étape C.7 : Renommer la version non-partitionnée
ALTER TABLE AUDIT_LOG_NOPART RENAME TO AUDIT_LOG;
ALTER TABLE AUDIT_LOG RENAME CONSTRAINT PK_AUDIT_LOG_NOPART TO PK_AUDIT_LOG;

-- Étape C.8 : Recréer les CHECK constraints (état pré-V086 = post-V068/V045)
ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ACTION_TYPE CHECK (
    ACTION_TYPE IN (
        'ACTION_CREATED', 'ACTION_UPDATED', 'ACTION_PUBLISHED',
        'ACTION_DISABLED', 'ACTION_ENABLED', 'ACTION_DELETED',
        'ACTION_DEACTIVATED', 'ACTION_REACTIVATED',
        'PROFILE_CREATED', 'PROFILE_UPDATED', 'PROFILE_DELETED', 'PROFILE_UPDATE_REJECTED',
        'INTEGRATION_CREATED', 'INTEGRATION_UPDATED', 'INTEGRATION_DELETED',
        'INTEGRATION_TYPE_CREATED', 'INTEGRATION_TYPE_UPDATED',
        'INTEGRATION_ACTION_CREATED', 'INTEGRATION_ACTION_UPDATED',
        'INTEGRATION_STATUS_UPDATED', 'INTEGRATION_MARKED_LEGACY',
        'EXECUTION_SUBMITTED', 'EXECUTION_STARTED', 'EXECUTION_RUNNING',
        'EXECUTION_COMPLETED', 'EXECUTION_FAILED', 'EXECUTION_CANCELLED',
        'EXECUTION_PENDING_APPROVAL', 'EXECUTION_APPROVED', 'EXECUTION_REJECTED',
        'EXECUTION_TARGET_FORBIDDEN', 'EXECUTION_INTEGRATION_ERROR',
        'EXECUTION_BLOCKED_INVALID_INTEGRATION', 'EXECUTION_DEPRECATED_INTEGRATION_WARNING',
        'WORKFLOW_STEP_BLOCKED_INVALID_INTEGRATION',
        'SERVICENOW_CHANGE_CREATED',
        'REMEDIATION_EXECUTION_CREATED',
        'AUTO_REMEDIATION_TRIGGERED', 'AUTO_REMEDIATION_SUCCESS', 'AUTO_REMEDIATION_FAILED',
        'SCHEDULED_EXECUTION_CREATED', 'SCHEDULED_EXECUTION_RECURRING_CREATED',
        'SCHEDULED_EXECUTION_EXECUTED', 'SCHEDULED_EXECUTION_CANCELLED',
        'SCHEDULED_EXECUTION_RECURRING_DISABLED',
        'USER_CREATED', 'USER_UPDATED', 'USER_LOGIN', 'USER_LOGOUT', 'USER_REFRESH',
        'FAVORITE_ADDED', 'FAVORITE_REMOVED',
        'EXECUTION_STEP_RETRY_ATTEMPT', 'EXECUTION_STEP_RETRY_SUCCESS',
        'EXECUTION_STEP_RETRY_EXHAUSTED', 'EXECUTION_STEP_RETRY_ABORTED',
        'FEATURE_FLAG_CREATED', 'FEATURE_FLAG_UPDATED'
    )
);

ALTER TABLE AUDIT_LOG ADD CONSTRAINT CK_AUDIT_LOG_ENTITY_TYPE CHECK (
    ENTITY_TYPE IN (
        'action', 'user', 'permission', 'execution',
        'scheduled_execution', 'integration', 'profile'
    )
);

-- Étape C.9 : Recréer les index (état pré-V086)
CREATE INDEX IDX_AUDIT_LOG_TIMESTAMP ON AUDIT_LOG(TIMESTAMP);
CREATE INDEX IDX_AUDIT_LOG_ENTITY ON AUDIT_LOG(ENTITY_TYPE, ENTITY_ID);
CREATE INDEX IDX_AUDIT_LOG_USER ON AUDIT_LOG(USER_ID);
CREATE INDEX IDX_AUDIT_LOG_ACTION_TYPE ON AUDIT_LOG(ACTION_TYPE);
CREATE INDEX IDX_AUDIT_LOG_CORRELATION ON AUDIT_LOG(CORRELATION_ID);
CREATE INDEX IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP ON AUDIT_LOG(ENTITY_TYPE, TIMESTAMP DESC);

-- Étape C.10 : Recréer le trigger d'immutabilité (SOC1/NFR8)
CREATE OR REPLACE TRIGGER TRG_AUDIT_LOG_IMMUTABLE
BEFORE UPDATE OR DELETE ON AUDIT_LOG
FOR EACH ROW
BEGIN
    RAISE_APPLICATION_ERROR(-20001,
        'AUDIT_LOG is immutable - UPDATE and DELETE operations are forbidden (SOC1/NFR8)');
END;
/

-- Étape C.11 : Nettoyage final
DROP TABLE AUDIT_LOG_ROLLBACK_CHECK PURGE;

-- Étape C.12 : Valider état final
SELECT PARTITIONED FROM USER_TABLES WHERE TABLE_NAME = 'AUDIT_LOG';
-- Doit être 'NO'
SELECT COUNT(*) AS FINAL_COUNT FROM AUDIT_LOG;
SELECT TRIGGER_NAME, STATUS FROM USER_TRIGGERS WHERE TABLE_NAME = 'AUDIT_LOG';
-- TRG_AUDIT_LOG_IMMUTABLE doit être ENABLED
*/

-- ===========================================================================
-- FLYWAY : Marquer V086 comme annulée dans flyway_schema_history
-- ===========================================================================
-- Après exécution du rollback, supprimer l'entrée V086 de Flyway pour permettre
-- une ré-exécution ou un saut de version :
--
-- DELETE FROM flyway_schema_history WHERE version = '086';
-- COMMIT;
--
-- Si vous souhaitez sauter définitivement V086 (sans re-exécuter) :
-- INSERT INTO flyway_schema_history (installed_rank, version, description, type, script,
--     checksum, installed_by, installed_on, execution_time, success)
-- VALUES (
--     (SELECT NVL(MAX(installed_rank),0)+1 FROM flyway_schema_history),
--     '086',
--     'partition_audit_log - ROLLED BACK',
--     'SQL',
--     'V086__partition_audit_log.sql',
--     0,
--     USER,
--     SYSDATE,
--     0,
--     1
-- );
-- COMMIT;
