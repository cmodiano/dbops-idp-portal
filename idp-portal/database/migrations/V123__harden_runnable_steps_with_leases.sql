-- V123: Renforcement RUNNABLE_STEPS avec leases et compteur de tentatives
-- Ref: Story 78.2 — Résilience aux pannes worker via lease temporel
--
-- Sans leases, un worker qui crashe après claim mais avant delete() bloque
-- le step indéfiniment. Avec leases, le step redevient disponible après
-- expiration de claimed_until (défaut: 5 min).

-- Ajout des colonnes lease
ALTER TABLE RUNNABLE_STEPS ADD (
    CLAIMED_UNTIL   TIMESTAMP,
    ATTEMPT_NO      NUMBER DEFAULT 0 NOT NULL,
    LAST_ERROR      VARCHAR2(4000),
    MAX_ATTEMPTS    NUMBER DEFAULT 3 NOT NULL
);

COMMENT ON COLUMN RUNNABLE_STEPS.CLAIMED_UNTIL IS 'Expiration du lease du worker. NULL = step disponible. Si < now = lease expiré (crash worker), step récupérable.';
COMMENT ON COLUMN RUNNABLE_STEPS.ATTEMPT_NO IS 'Nombre de tentatives cumulées (incrémenté à chaque claim, jamais réinitialisé).';
COMMENT ON COLUMN RUNNABLE_STEPS.LAST_ERROR IS 'Dernière erreur rencontrée lors de l''exécution du step (max 4000 chars Oracle).';
COMMENT ON COLUMN RUNNABLE_STEPS.MAX_ATTEMPTS IS 'Nombre maximum de tentatives avant abandon (défaut: 3).';

-- Remplacement de l'index claim : le nouveau filtre utilise CLAIMED_UNTIL au lieu de CLAIMED_AT
DROP INDEX IDX_RUNNABLE_STEPS_UNCLAIMED;

CREATE INDEX IDX_RUNNABLE_STEPS_LEASE ON RUNNABLE_STEPS(
    ELIGIBLE_AT,
    CLAIMED_UNTIL,
    PRIORITY
);
