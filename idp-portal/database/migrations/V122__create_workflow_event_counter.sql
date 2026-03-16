-- V122: Table WORKFLOW_EVENT_COUNTER — allocation de séquence atomique pour WORKFLOW_EVENTS
-- Ref: Story 78.1 — Élimination de la race condition MAX()+1 sous émetteurs concurrents
--
-- Chaque exécution obtient une ligne dans cette table. L'incrémentation de
-- LAST_SEQUENCE_NUM se fait via SELECT ... FOR UPDATE (row-level lock Oracle),
-- garantissant une séquence strictement croissante sans doublons ni trous,
-- même si plusieurs threads émettent simultanément pour la même execution_id.

CREATE TABLE WORKFLOW_EVENT_COUNTER (
    EXECUTION_ID        NUMBER NOT NULL,
    LAST_SEQUENCE_NUM   NUMBER DEFAULT 0 NOT NULL,

    CONSTRAINT PK_WORKFLOW_EVENT_COUNTER PRIMARY KEY (EXECUTION_ID),
    CONSTRAINT FK_WF_EVENT_COUNTER_EXEC FOREIGN KEY (EXECUTION_ID)
        REFERENCES EXECUTIONS(ID) ON DELETE CASCADE,
    CONSTRAINT CK_WF_EVENT_COUNTER_SEQ CHECK (LAST_SEQUENCE_NUM >= 0)
);

COMMENT ON TABLE WORKFLOW_EVENT_COUNTER IS 'Compteur de séquence atomique par exécution pour WORKFLOW_EVENTS. Une seule ligne par execution_id ; incrément via SELECT FOR UPDATE.';
COMMENT ON COLUMN WORKFLOW_EVENT_COUNTER.EXECUTION_ID IS 'FK vers EXECUTIONS(ID) — clé primaire de la table.';
COMMENT ON COLUMN WORKFLOW_EVENT_COUNTER.LAST_SEQUENCE_NUM IS 'Dernier numéro de séquence alloué pour cette exécution. Initialisé à 0, incrémenté de 1 à chaque événement.';
