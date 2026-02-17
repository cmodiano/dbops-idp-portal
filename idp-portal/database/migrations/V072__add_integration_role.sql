-- V072: Add INTEGRATION_ROLE column to INTEGRATION_TYPE_CATALOGUE
-- Story 29.1: Distinguish platforms (execution) from services (consumption)

ALTER TABLE INTEGRATION_TYPE_CATALOGUE
ADD INTEGRATION_ROLE VARCHAR2(20) DEFAULT 'platform' NOT NULL;

ALTER TABLE INTEGRATION_TYPE_CATALOGUE
ADD CONSTRAINT CHK_INTEGRATION_ROLE
    CHECK (INTEGRATION_ROLE IN ('platform', 'service'));

COMMENT ON COLUMN INTEGRATION_TYPE_CATALOGUE.INTEGRATION_ROLE IS
    'Role de l''integration: platform (execution) ou service (consommation)';

-- Set services explicitly
UPDATE INTEGRATION_TYPE_CATALOGUE SET INTEGRATION_ROLE = 'service' WHERE CODE IN ('vault', 'servicenow', 'jira', 'splunk');
