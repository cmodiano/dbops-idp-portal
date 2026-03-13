-- Story 76.3: Ajouter UPDATED_AT sur la table EXECUTIONS
-- Permet la détection de staleness par heartbeat (dernière activité = updated_at si set, sinon created_at).
--
-- Rétrocompatibilité : colonne nullable, les exécutions existantes ont NULL (fallback sur created_at).
-- Convention : TIMESTAMP plain UTC (comme CREATED_AT, V048).

ALTER TABLE EXECUTIONS ADD (UPDATED_AT TIMESTAMP);

COMMENT ON COLUMN EXECUTIONS.UPDATED_AT IS 'Last activity timestamp (heartbeat). NULL for pre-76.3 executions; used with created_at for staleness detection.';

-- GLOBAL: staleness query filters by updated_at across partitions (reconcile task)
CREATE INDEX IDX_EXECUTIONS_UPDATED_AT ON EXECUTIONS (UPDATED_AT) GLOBAL;
