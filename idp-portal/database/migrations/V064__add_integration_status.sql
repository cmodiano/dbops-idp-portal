-- V064: Add STATUS column to INTEGRATIONS table
-- Django integrations/0004_add_integration_status - Integration validation state machine
-- Values: valid (default), invalid, deprecated

ALTER TABLE INTEGRATIONS ADD STATUS VARCHAR2(20) DEFAULT 'valid' NOT NULL;

ALTER TABLE INTEGRATIONS ADD CONSTRAINT CK_INTEGRATIONS_STATUS CHECK (
    STATUS IN ('valid', 'invalid', 'deprecated')
);

CREATE INDEX IDX_INTEGRATION_STATUS ON INTEGRATIONS(STATUS);

COMMENT ON COLUMN INTEGRATIONS.STATUS IS 'Integration validation status: valid (active), invalid (config error), deprecated (no longer supported)';
