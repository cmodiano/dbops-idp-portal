-- V080: Allow status=disabled without soft-delete (deleted_at/deletion_reason)
-- Integration-deletion flow disables actions with status+updated_at only; rationale in audit.
-- Soft-delete (deleted_at/deletion_reason) remains for explicit deactivate_action.

ALTER TABLE ACTIONS_CATALOG DROP CONSTRAINT CK_ACTIONS_SOFT_DELETE_CONSISTENCY;

ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_SOFT_DELETE_CONSISTENCY CHECK (
    (STATUS = 'disabled')
    OR
    (DELETED_AT IS NULL AND STATUS IN ('draft', 'published'))
);

COMMENT ON COLUMN ACTIONS_CATALOG.DELETED_AT IS 'Story 18.1 V080: Set when action is soft-deactivated (deactivate_action). NULL when disabled only (e.g. integration deleted).';
