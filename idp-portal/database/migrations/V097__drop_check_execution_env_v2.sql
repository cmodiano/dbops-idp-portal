-- V097: Supprime la contrainte CHECK restrictive sur EXECUTIONS.ENVIRONMENT (Story 53.2)
--
-- Contexte :
--   V053 avait déjà droppé CHK_EXECUTION_ENV et CHK_SCHEDULED_ENV.
--   V084 (partitionnement, Epic 40) a ré-ajouté CHK_EXECUTION_ENV sur EXECUTIONS
--   avec la liste codée en dur : CHECK (ENVIRONMENT IN ('dev', 'staging', 'prod')).
--   L'inventaire est désormais la seule source de vérité pour les valeurs d'environnement
--   valides (Epic 53). La validation applicative remplace la contrainte Oracle.
--
-- Note :
--   CHK_SCHEDULED_ENV sur SCHEDULED_EXECUTIONS a été droppée par V053 et n'a pas été
--   ré-ajoutée par V084 — aucune action nécessaire sur cette table.
--
-- Idempotence :
--   Oracle ne supporte pas DROP CONSTRAINT IF EXISTS. Le bloc PL/SQL ci-dessous
--   ignore ORA-02443 (contrainte inexistante) pour rendre la migration résiliente
--   aux environnements où la contrainte aurait déjà été supprimée manuellement.

BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS DROP CONSTRAINT CHK_EXECUTION_ENV';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE != -2443 THEN
            RAISE;
        END IF;
END;
/
