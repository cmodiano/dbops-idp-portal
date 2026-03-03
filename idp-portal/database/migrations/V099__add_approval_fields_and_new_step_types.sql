-- Story 57.1: ExecutionStep — champs d'approbation granulaire et nouveaux types (ADR-007)
-- Référence: V030 (pattern ajout colonnes + FK), V025/V067 (contrainte CHK_STEP_TYPE)

-- 1. Ajouter les colonnes d'approbation à EXECUTION_STEPS
ALTER TABLE EXECUTION_STEPS ADD (
    APPROVED_BY     NUMBER(10),
    APPROVED_AT     TIMESTAMP WITH TIME ZONE,
    APPROVAL_COMMENT VARCHAR2(1000)
);

-- 2. Contrainte FK vers USERS(ID) avec ON DELETE SET NULL (cohérent avec on_delete=SET_NULL Django)
ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT FK_EXEC_STEPS_APPROVED_BY
    FOREIGN KEY (APPROVED_BY) REFERENCES USERS(ID) ON DELETE SET NULL;

-- 3. Mettre à jour la contrainte CHK_STEP_TYPE pour inclure les 4 nouveaux types ADR-007
ALTER TABLE EXECUTION_STEPS DROP CONSTRAINT CHK_STEP_TYPE;
ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT CHK_STEP_TYPE
    CHECK (STEP_TYPE IN (
        'vault', 'servicenow', 'platform', 'prerequisite', 'verification',
        'service_call', 'http_request', 'evaluation', 'gate'
    ));

-- 4. Commentaires sur les nouvelles colonnes
COMMENT ON COLUMN EXECUTION_STEPS.APPROVED_BY IS 'FK vers USERS(ID) — utilisateur ayant approuvé ce step (ADR-007)';
COMMENT ON COLUMN EXECUTION_STEPS.APPROVED_AT IS 'Date/heure de l''approbation du step (ADR-007)';
COMMENT ON COLUMN EXECUTION_STEPS.APPROVAL_COMMENT IS 'Commentaire d''approbation du step, max 1000 caractères (ADR-007)';
