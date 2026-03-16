-- V127: Tables WORKFLOW_DEFINITIONS, WORKFLOW_STEPS, WORKFLOW_STEP_EDGES
-- Story 78.10 — Normalisation des définitions de workflow
--
-- Extraction des workflow step definitions depuis le JSON CLOB
-- (ACTIONS_CATALOG.EXECUTION_STEPS) vers des tables relationnelles
-- permettant requêtes SQL directes, indexes et contraintes DB.
--
-- CREATED_AT / UPDATED_AT : UTC via SYSTIMESTAMP AT TIME ZONE 'UTC'.

-- ============================================================
-- 1. WORKFLOW_DEFINITIONS — one-to-one avec ACTIONS_CATALOG (type workflow)
-- ============================================================

CREATE TABLE WORKFLOW_DEFINITIONS (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ACTION_ID       NUMBER,
    VERSION         NUMBER DEFAULT 1 NOT NULL,
    CREATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    UPDATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    CONSTRAINT FK_WF_DEF_ACTION FOREIGN KEY (ACTION_ID)
        REFERENCES ACTIONS_CATALOG(ID) ON DELETE CASCADE
);

COMMENT ON TABLE WORKFLOW_DEFINITIONS IS 'Définition normalisée d''un workflow — one-to-one avec ACTIONS_CATALOG pour item_type=workflow.';
COMMENT ON COLUMN WORKFLOW_DEFINITIONS.ACTION_ID IS 'FK vers ACTIONS_CATALOG — action de type workflow associée.';
COMMENT ON COLUMN WORKFLOW_DEFINITIONS.VERSION IS 'Version de la définition (incrémentée à chaque modification).';

-- ============================================================
-- 2. WORKFLOW_STEPS — une ligne par step de workflow
-- ============================================================

CREATE TABLE WORKFLOW_STEPS (
    ID                          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    WORKFLOW_DEFINITION_ID      NUMBER NOT NULL,
    STEP_ID                     VARCHAR2(255) NOT NULL,
    STEP_ORDER                  NUMBER NOT NULL,
    STEP_NAME                   VARCHAR2(255) NOT NULL,
    STEP_TYPE                   VARCHAR2(50) NOT NULL,
    REFERENCED_ACTION_ID        NUMBER,
    INTEGRATION_TYPE            VARCHAR2(100),
    OPERATION                   VARCHAR2(255),
    INPUT_MAPPING               CLOB,
    OUTPUT_MAPPING              CLOB,
    CONDITION                   CLOB,
    RETRY_ENABLED               NUMBER(1) DEFAULT 0 NOT NULL,
    RETRY_MAX_ATTEMPTS          NUMBER,
    RETRY_INTERVAL_SECONDS      NUMBER,
    RETRY_BACKOFF_MULTIPLIER    NUMBER(5,2),
    JOIN_POLICY                 VARCHAR2(50),
    CONSTRAINT FK_WF_STEPS_DEF FOREIGN KEY (WORKFLOW_DEFINITION_ID)
        REFERENCES WORKFLOW_DEFINITIONS(ID) ON DELETE CASCADE,
    CONSTRAINT FK_WF_STEPS_REF_ACTION FOREIGN KEY (REFERENCED_ACTION_ID)
        REFERENCES ACTIONS_CATALOG(ID) ON DELETE SET NULL
);

COMMENT ON TABLE WORKFLOW_STEPS IS 'Steps individuels d''un workflow — une ligne par étape.';
COMMENT ON COLUMN WORKFLOW_STEPS.STEP_ID IS 'Identifiant stable du step (UUID) — utilisé pour le routage success/error.';
COMMENT ON COLUMN WORKFLOW_STEPS.STEP_ORDER IS 'Ordre d''exécution du step dans le workflow.';
COMMENT ON COLUMN WORKFLOW_STEPS.STEP_TYPE IS 'Type de step: platform, service_call, http_request, evaluation, gate, schedule_execution.';
COMMENT ON COLUMN WORKFLOW_STEPS.REFERENCED_ACTION_ID IS 'FK vers ACTIONS_CATALOG — action référencée pour exécution (nullable pour steps sans action).';
COMMENT ON COLUMN WORKFLOW_STEPS.INTEGRATION_TYPE IS 'Type d''intégration (ex: servicenow, vault) pour les steps service_call.';
COMMENT ON COLUMN WORKFLOW_STEPS.OPERATION IS 'Opération spécifique à exécuter (ex: create_change).';
COMMENT ON COLUMN WORKFLOW_STEPS.INPUT_MAPPING IS 'Mapping JSON des entrées du step (Jinja2 templates).';
COMMENT ON COLUMN WORKFLOW_STEPS.OUTPUT_MAPPING IS 'Mapping JSON des sorties du step (JSONPath).';
COMMENT ON COLUMN WORKFLOW_STEPS.CONDITION IS 'Condition d''exécution du step (Jinja2/JSON).';
COMMENT ON COLUMN WORKFLOW_STEPS.RETRY_ENABLED IS 'Retry activé (0=non, 1=oui).';
COMMENT ON COLUMN WORKFLOW_STEPS.JOIN_POLICY IS 'Politique de join pour convergence: all_success, one_success, all_done, all_failed, one_failed.';

-- ============================================================
-- 3. WORKFLOW_STEP_EDGES — arêtes du graphe (success / error)
-- ============================================================

CREATE TABLE WORKFLOW_STEP_EDGES (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    FROM_STEP_ID    NUMBER NOT NULL,
    TO_STEP_ID      NUMBER NOT NULL,
    EDGE_TYPE       VARCHAR2(20) NOT NULL,
    CONSTRAINT FK_WF_EDGES_FROM FOREIGN KEY (FROM_STEP_ID)
        REFERENCES WORKFLOW_STEPS(ID) ON DELETE CASCADE,
    CONSTRAINT FK_WF_EDGES_TO FOREIGN KEY (TO_STEP_ID)
        REFERENCES WORKFLOW_STEPS(ID) ON DELETE CASCADE,
    CONSTRAINT UK_WF_EDGES_FROM_TO_TYPE UNIQUE (FROM_STEP_ID, TO_STEP_ID, EDGE_TYPE),
    CONSTRAINT CK_WF_EDGES_EDGE_TYPE CHECK (EDGE_TYPE IN ('success', 'error'))
);

COMMENT ON TABLE WORKFLOW_STEP_EDGES IS 'Arêtes du graphe de workflow — transitions success/error entre steps.';
COMMENT ON COLUMN WORKFLOW_STEP_EDGES.FROM_STEP_ID IS 'FK vers WORKFLOW_STEPS — step source de la transition.';
COMMENT ON COLUMN WORKFLOW_STEP_EDGES.TO_STEP_ID IS 'FK vers WORKFLOW_STEPS — step destination de la transition.';
COMMENT ON COLUMN WORKFLOW_STEP_EDGES.EDGE_TYPE IS 'Type de transition: success ou error.';

-- ============================================================
-- 4. Indexes
-- ============================================================

CREATE INDEX IDX_WF_STEPS_DEF_ID ON WORKFLOW_STEPS(WORKFLOW_DEFINITION_ID);
CREATE INDEX IDX_WF_STEPS_STEP_ID ON WORKFLOW_STEPS(STEP_ID);
CREATE INDEX IDX_WF_EDGES_FROM ON WORKFLOW_STEP_EDGES(FROM_STEP_ID);
CREATE INDEX IDX_WF_EDGES_TO ON WORKFLOW_STEP_EDGES(TO_STEP_ID);
