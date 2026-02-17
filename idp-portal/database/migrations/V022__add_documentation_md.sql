-- V022: Add DOCUMENTATION_MD column to ACTIONS_CATALOG
-- Story 3.4 - Documentation contextuelle d'une action
-- FR12: Tout utilisateur peut accéder à la documentation contextuelle d'une action

ALTER TABLE ACTIONS_CATALOG ADD (
    DOCUMENTATION_MD CLOB
);

COMMENT ON COLUMN ACTIONS_CATALOG.DOCUMENTATION_MD IS 'Markdown documentation for the action. Rendered in the frontend drawer. Supports headings, lists, code blocks, and tables.';
