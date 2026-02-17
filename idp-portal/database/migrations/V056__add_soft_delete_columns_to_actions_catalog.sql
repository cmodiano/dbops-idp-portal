-- V056: Add soft-delete columns to ACTIONS_CATALOG
-- Story 18.1 - Désactivation d'actions (soft delete: deleted_at, deleted_by, deletion_reason)
-- Aligns Oracle schema with Django catalog migration 0004_add_soft_delete_columns

-- Add columns for soft delete
ALTER TABLE ACTIONS_CATALOG ADD (
    DELETED_AT      TIMESTAMP NULL,
    DELETED_BY      NUMBER NULL,
    DELETION_REASON VARCHAR2(500) NULL
);

-- FK: deleted_by references USERS
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT FK_ACTIONS_CATALOG_DELETED_BY
    FOREIGN KEY (DELETED_BY) REFERENCES USERS(ID);

-- Index for filtering by deleted_at (Django: idx_actions_deleted_at)
CREATE INDEX IDX_ACTIONS_CATALOG_DELETED_AT ON ACTIONS_CATALOG(DELETED_AT);

-- Backfill: existing disabled rows must have DELETED_AT set before adding the check constraint
UPDATE ACTIONS_CATALOG
SET DELETED_AT = COALESCE(UPDATED_AT, CREATED_AT),
    DELETION_REASON = 'Migré (désactivé avant soft delete)'
WHERE STATUS = 'disabled' AND DELETED_AT IS NULL;

COMMIT;

-- Consistency: disabled rows must have deleted_at set; draft/published must have deleted_at null
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_SOFT_DELETE_CONSISTENCY CHECK (
    (DELETED_AT IS NOT NULL AND STATUS = 'disabled')
    OR
    (DELETED_AT IS NULL AND STATUS IN ('draft', 'published'))
);

COMMENT ON COLUMN ACTIONS_CATALOG.DELETED_AT IS 'Story 18.1: When the action was disabled (soft delete).';
COMMENT ON COLUMN ACTIONS_CATALOG.DELETED_BY IS 'Story 18.1: User who disabled the action (FK USERS).';
COMMENT ON COLUMN ACTIONS_CATALOG.DELETION_REASON IS 'Story 18.1: Reason for deactivation (max 500 chars).';
