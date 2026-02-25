-- V084 ROLLBACK : Restaurer EXECUTIONS non-partitionnée
-- Story 40.2 - Epic 40: Partitionnement et rétention tables performance
--
-- USAGE DBA MANUEL UNIQUEMENT — Ce script n'est PAS exécuté par Flyway.
-- À utiliser en cas de problème après exécution de V084__partition_executions.sql.
--
-- PRÉREQUIS :
--   1. Identifier le scénario applicable (voir ci-dessous)
--   2. Effectuer un backup avant exécution
--   3. Planifier une fenêtre de maintenance (durée estimée: 4-8h selon volume)
--   4. Valider sur DEV/PREPROD avant application PROD
--
-- SCÉNARIOS DE ROLLBACK :
--   Scénario A : V084 a échoué avant la Phase 5 (EXECUTIONS_OLD n'existe pas)
--     → EXECUTIONS originale encore intacte, EXECUTIONS_NEW à supprimer
--     → Exécuter : Section A ci-dessous
--   Scénario B : V084 a échoué pendant/après Phase 5 (EXECUTIONS_OLD existe)
--     → EXECUTIONS_OLD existe, la table EXECUTIONS est la version partitionnée (potentiellement partielle)
--     → Exécuter : Section B ci-dessous (rollback complet)
--   Scénario C : V084 s'est terminée avec succès (EXECUTIONS_OLD a été supprimée)
--     → Rollback doit recréer la table non-partitionnée depuis EXECUTIONS partitionnée
--     → Exécuter : Section C ci-dessous (rollback post-succès)
--
-- ===========================================================================
-- SECTION A : Nettoyage si échec avant Phase 5 (EXECUTIONS intacte)
-- ===========================================================================
-- Vérifier d'abord : SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME IN ('EXECUTIONS','EXECUTIONS_NEW','EXECUTIONS_OLD');
-- Si EXECUTIONS existe et EXECUTIONS_OLD n'existe pas → Section A applicable

/*
-- Supprimer EXECUTIONS_NEW (en cours de création, données peut-être incomplètes)
DROP TABLE EXECUTIONS_NEW PURGE;

-- Supprimer la table de contrôle si elle existe
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE EXECUTIONS_MIGRATION_CHECK PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN RAISE; END IF;  -- ORA-00942: table or view does not exist
END;
/

-- EXECUTIONS originale est intacte, aucune autre action requise.
-- Flyway doit être réinitialisé pour permettre une ré-exécution de V084 corrigée.
*/

-- ===========================================================================
-- SECTION B : Rollback complet depuis EXECUTIONS_OLD (échec mid-migration)
-- ===========================================================================
-- Applicable si EXECUTIONS_OLD existe (Phase 5 a été exécutée mais V084 a échoué ensuite)

/*
-- Étape B.1 : Désactiver les FK enfant sur la version partitionnée (peut avoir été réactivée partiellement)
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE EXECUTION_STEPS DISABLE CONSTRAINT FK_EXEC_STEPS_EXECUTION';
EXCEPTION
    WHEN OTHERS THEN NULL;  -- Ignorer si déjà désactivée ou si la contrainte n'existe pas encore
END;
/
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE EXECUTION_TARGETS DISABLE CONSTRAINT FK_EXEC_TARGETS_EXECUTION';
EXCEPTION
    WHEN OTHERS THEN NULL;
END;
/

-- Étape B.2 : Supprimer la version partitionnée (EXECUTIONS = anciennement EXECUTIONS_NEW)
DROP TABLE EXECUTIONS PURGE;

-- Étape B.3 : Renommer EXECUTIONS_OLD → EXECUTIONS
ALTER TABLE EXECUTIONS_OLD RENAME TO EXECUTIONS;

-- Étape B.4 : Vérifier/Réactiver les FK enfant
-- Les contraintes FK sur EXECUTION_STEPS et EXECUTION_TARGETS pointent maintenant
-- à nouveau vers EXECUTIONS (l'originale). Les activer si elles étaient désactivées.
ALTER TABLE EXECUTION_STEPS ENABLE CONSTRAINT FK_EXEC_STEPS_EXECUTION;
ALTER TABLE EXECUTION_TARGETS ENABLE CONSTRAINT FK_EXEC_TARGETS_EXECUTION;

-- Étape B.5 : Supprimer la table de contrôle si elle existe
BEGIN
    EXECUTE IMMEDIATE 'DROP TABLE EXECUTIONS_MIGRATION_CHECK PURGE';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -942 THEN RAISE; END IF;
END;
/

-- Étape B.6 : Valider
SELECT COUNT(*) AS EXECUTIONS_COUNT FROM EXECUTIONS;
SELECT PARTITIONED FROM USER_TABLES WHERE TABLE_NAME = 'EXECUTIONS';
-- PARTITIONED doit être 'NO'
*/

-- ===========================================================================
-- SECTION C : Rollback post-succès (EXECUTIONS_OLD supprimée)
-- ===========================================================================
-- Applicable si V084 s'est terminée avec succès et que EXECUTIONS_OLD n'existe plus.
-- Cette section recrée une table non-partitionnée depuis la table partitionnée actuelle.
-- ATTENTION : Opération longue selon volume (estimation : 4-8h pour volumes PROD)

/*
-- Étape C.0 : Vérification
DECLARE
    v_partitioned VARCHAR2(3);
BEGIN
    SELECT PARTITIONED INTO v_partitioned FROM USER_TABLES WHERE TABLE_NAME = 'EXECUTIONS';
    IF v_partitioned != 'YES' THEN
        RAISE_APPLICATION_ERROR(-20010, 'EXECUTIONS n''est pas partitionnée - rollback inutile');
    END IF;
    DBMS_OUTPUT.PUT_LINE('EXECUTIONS est bien partitionnée - rollback applicable');
END;
/

-- Étape C.1 : Capturer COUNT de référence
CREATE TABLE EXECUTIONS_ROLLBACK_CHECK AS
    SELECT COUNT(*) AS ROW_COUNT FROM EXECUTIONS;

-- Étape C.2 : Créer la table non-partitionnée de destination
CREATE TABLE EXECUTIONS_NOPART (
    ID              NUMBER GENERATED BY DEFAULT ON NULL AS IDENTITY,
    ACTION_ID       NUMBER NOT NULL,
    USER_ID         NUMBER NOT NULL,
    ENVIRONMENT     VARCHAR2(50) NOT NULL,
    PARAMETERS      CLOB,
    STATUS          VARCHAR2(20) DEFAULT 'SUBMITTED' NOT NULL,
    SERVICENOW_CHANGE_ID VARCHAR2(100),
    STARTED_AT      TIMESTAMP,
    COMPLETED_AT    TIMESTAMP,
    CREATED_AT      TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    APPROVED_BY     NUMBER(10),
    APPROVED_AT     TIMESTAMP,
    APPROVAL_COMMENT VARCHAR2(1000),
    PARENT_EXECUTION_ID NUMBER(19),
    ERROR_MESSAGE   CLOB,
    CONSTRAINT PK_EXECUTIONS_NOPART PRIMARY KEY (ID)
);

-- Étape C.3 : Copier les données
INSERT /*+ APPEND PARALLEL(4) */ INTO EXECUTIONS_NOPART
    (ID, ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, STATUS,
     SERVICENOW_CHANGE_ID, STARTED_AT, COMPLETED_AT, CREATED_AT,
     APPROVED_BY, APPROVED_AT, APPROVAL_COMMENT,
     PARENT_EXECUTION_ID, ERROR_MESSAGE)
SELECT  ID, ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, STATUS,
        SERVICENOW_CHANGE_ID, STARTED_AT, COMPLETED_AT, CREATED_AT,
        APPROVED_BY, APPROVED_AT, APPROVAL_COMMENT,
        PARENT_EXECUTION_ID, ERROR_MESSAGE
FROM EXECUTIONS;
COMMIT;

-- Recaler la séquence IDENTITY
DECLARE
    v_max NUMBER;
BEGIN
    SELECT NVL(MAX(ID), 0) INTO v_max FROM EXECUTIONS_NOPART;
    IF v_max > 0 THEN
        EXECUTE IMMEDIATE
            'ALTER TABLE EXECUTIONS_NOPART MODIFY ID GENERATED BY DEFAULT ON NULL AS IDENTITY (START WITH '
            || (v_max + 1) || ' INCREMENT BY 1 NOCACHE)';
    END IF;
END;
/

-- Étape C.4 : Valider COUNT avant renommage
DECLARE
    v_orig NUMBER;
    v_new  NUMBER;
BEGIN
    SELECT ROW_COUNT INTO v_orig FROM EXECUTIONS_ROLLBACK_CHECK;
    SELECT COUNT(*) INTO v_new FROM EXECUTIONS_NOPART;
    IF v_new != v_orig THEN
        RAISE_APPLICATION_ERROR(-20011,
            'ROLLBACK COUNT MISMATCH: original=' || v_orig || ', restored=' || v_new);
    END IF;
    DBMS_OUTPUT.PUT_LINE('Rollback count validated: ' || v_new || ' rows');
END;
/

-- Étape C.5 : Désactiver FK enfant
ALTER TABLE EXECUTION_STEPS DISABLE CONSTRAINT FK_EXEC_STEPS_EXECUTION;
ALTER TABLE EXECUTION_TARGETS DISABLE CONSTRAINT FK_EXEC_TARGETS_EXECUTION;

-- Étape C.6 : Supprimer la version partitionnée
DROP TABLE EXECUTIONS PURGE;

-- Étape C.7 : Renommer la version non-partitionnée
ALTER TABLE EXECUTIONS_NOPART RENAME TO EXECUTIONS;
ALTER TABLE EXECUTIONS RENAME CONSTRAINT PK_EXECUTIONS_NOPART TO PK_EXECUTIONS;

-- Étape C.8 : Recréer les FK applicatives sur EXECUTIONS (état pré-V084)
ALTER TABLE EXECUTIONS ADD CONSTRAINT FK_EXECUTIONS_ACTION
    FOREIGN KEY (ACTION_ID) REFERENCES ACTIONS_CATALOG(ID);
ALTER TABLE EXECUTIONS ADD CONSTRAINT FK_EXECUTIONS_USER
    FOREIGN KEY (USER_ID) REFERENCES USERS(ID);
ALTER TABLE EXECUTIONS ADD CONSTRAINT FK_EXECUTIONS_APPROVED_BY
    FOREIGN KEY (APPROVED_BY) REFERENCES USERS(ID);
ALTER TABLE EXECUTIONS ADD CONSTRAINT FK_EXECUTIONS_PARENT
    FOREIGN KEY (PARENT_EXECUTION_ID) REFERENCES EXECUTIONS(ID) ON DELETE SET NULL;

-- Étape C.9 : Recréer les CHECK constraints (état pré-V084, version V057)
ALTER TABLE EXECUTIONS ADD CONSTRAINT CHK_EXECUTION_STATUS
    CHECK (STATUS IN (
        'SUBMITTED', 'INTEGRATION_ERROR', 'PENDING_APPROVAL',
        'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'
    ));
ALTER TABLE EXECUTIONS ADD CONSTRAINT CHK_EXECUTION_ENV
    CHECK (ENVIRONMENT IN ('dev', 'staging', 'prod'));

-- Étape C.10 : Réactiver FK enfant
ALTER TABLE EXECUTION_STEPS ENABLE CONSTRAINT FK_EXEC_STEPS_EXECUTION;
ALTER TABLE EXECUTION_TARGETS ENABLE CONSTRAINT FK_EXEC_TARGETS_EXECUTION;

-- Étape C.11 : Recréer les index (état pré-V084)
CREATE INDEX IDX_EXECUTIONS_STATUS       ON EXECUTIONS(STATUS);
CREATE INDEX IDX_EXECUTIONS_USER_ID      ON EXECUTIONS(USER_ID);
CREATE INDEX IDX_EXECUTIONS_ACTION_ID    ON EXECUTIONS(ACTION_ID);
CREATE INDEX IDX_EXECUTIONS_CREATED_AT   ON EXECUTIONS(CREATED_AT);
CREATE INDEX IDX_EXEC_ACTION_CREATED     ON EXECUTIONS(ACTION_ID, CREATED_AT);
CREATE INDEX IDX_EXECUTIONS_PARENT_ID    ON EXECUTIONS(PARENT_EXECUTION_ID);
CREATE INDEX IDX_EXECUTIONS_PENDING_APPROVAL ON EXECUTIONS(
    CASE WHEN STATUS = 'PENDING_APPROVAL' THEN ID END
);

-- Étape C.12 : Nettoyage final
DROP TABLE EXECUTIONS_ROLLBACK_CHECK PURGE;

-- Étape C.13 : Valider état final
SELECT PARTITIONED FROM USER_TABLES WHERE TABLE_NAME = 'EXECUTIONS';
-- Doit être 'NO'
SELECT COUNT(*) AS FINAL_COUNT FROM EXECUTIONS;
-- Doit correspondre au COUNT capturé avant V084
*/

-- ===========================================================================
-- FLYWAY : Marquer V084 comme annulée dans flyway_schema_history
-- ===========================================================================
-- Après exécution du rollback, supprimer l'entrée V084 de Flyway pour permettre
-- une ré-exécution ou un saut de version :
--
-- DELETE FROM flyway_schema_history WHERE version = '084';
-- COMMIT;
--
-- Puis si vous souhaitez sauter définitivement V084 (sans re-exécuter) :
-- INSERT INTO flyway_schema_history (installed_rank, version, description, type, script,
--     checksum, installed_by, installed_on, execution_time, success)
-- VALUES (
--     (SELECT NVL(MAX(installed_rank),0)+1 FROM flyway_schema_history),
--     '084',
--     'partition_executions - ROLLED BACK',
--     'SQL',
--     'V084__partition_executions.sql',
--     0,
--     USER,
--     SYSDATE,
--     0,
--     1
-- );
-- COMMIT;
