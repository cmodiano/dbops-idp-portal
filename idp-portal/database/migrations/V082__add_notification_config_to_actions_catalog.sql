-- Story 31.8: Add notification_config JSON field to ACTIONS_CATALOG
-- Stores notification channels configuration (email, Teams, page) and conditions
ALTER TABLE ACTIONS_CATALOG ADD (NOTIFICATION_CONFIG CLOB CHECK (NOTIFICATION_CONFIG IS JSON));

COMMENT ON COLUMN ACTIONS_CATALOG.NOTIFICATION_CONFIG IS
'JSON configuration des notifications : canaux (email, teams, page_dba), conditions et page_individual_enabled. Story 31.8.';
