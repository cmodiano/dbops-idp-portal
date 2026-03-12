-- Story 72.1: Ajouter CORRELATION_ID sur la table EXECUTIONS
-- Permet de propager et tracer le correlation_id sur tout le cycle d'exécution
-- (soumission, workflow, Celery, polling, gates, audit) via un seul identifiant.
--
-- Rétrocompatibilité : colonne nullable, les exécutions existantes ont NULL.
-- L'index IDX_AUDIT_LOG_CORRELATION existe déjà sur AUDIT_LOG (V028).

ALTER TABLE EXECUTIONS ADD CORRELATION_ID VARCHAR2(64);

-- Index pour recherche rapide par correlation_id (Splunk, audit)
CREATE INDEX IDX_EXECUTIONS_CORRELATION ON EXECUTIONS (CORRELATION_ID);
