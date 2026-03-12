-- V118: Add REJECTED_BY and REJECTED_AT to EXECUTION_STEPS
-- Persists the rejecting actor and timestamp when a gate step is rejected (ADR-007).
-- Mirrors approved_by/approved_at for approval; enables audit trail for rejections.

ALTER TABLE EXECUTION_STEPS ADD (
    REJECTED_BY     NUMBER(10),
    REJECTED_AT     TIMESTAMP
);

ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT FK_EXEC_STEPS_REJECTED_BY
    FOREIGN KEY (REJECTED_BY) REFERENCES USERS(ID) ON DELETE SET NULL;

COMMENT ON COLUMN EXECUTION_STEPS.REJECTED_BY IS 'FK vers USERS(ID) — utilisateur ayant rejeté ce step (gate rejection, ADR-007). V118.';
COMMENT ON COLUMN EXECUTION_STEPS.REJECTED_AT IS 'Date/heure du rejet du step (gate rejection). V118.';
