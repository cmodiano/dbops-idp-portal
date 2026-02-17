-- Migration V020: Create INTEGRATIONS table for remote platform configuration
-- Story 2.27 - Backend Integrations (AAP, Terraform, ServiceNow, etc.)
-- AC1: ID (identity), TYPE (enum), NAME (unique), BASE_URL, CREDENTIAL_REF, ICON, CREATED_AT, UPDATED_AT

CREATE TABLE INTEGRATIONS (
    ID NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    TYPE VARCHAR2(50) NOT NULL CONSTRAINT CK_INTEGRATIONS_TYPE CHECK (TYPE IN ('aap', 'servicenow', 'terraform', 'azuredevops', 'jira', 'github_actions')),
    NAME VARCHAR2(255) NOT NULL CONSTRAINT UK_INTEGRATIONS_NAME UNIQUE,
    BASE_URL VARCHAR2(2000) NOT NULL,
    CREDENTIAL_REF VARCHAR2(500),
    ICON VARCHAR2(500),
    CREATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    UPDATED_AT TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
);

-- Index for listing integrations by type
CREATE INDEX IDX_INTEGRATIONS_TYPE ON INTEGRATIONS(TYPE);

COMMENT ON TABLE INTEGRATIONS IS 'Remote platform configuration for execution (AAP, ServiceNow, Terraform, etc.)';
COMMENT ON COLUMN INTEGRATIONS.ID IS 'Primary key (identity column)';
COMMENT ON COLUMN INTEGRATIONS.TYPE IS 'Integration type: aap, servicenow, terraform, azuredevops, jira, github_actions';
COMMENT ON COLUMN INTEGRATIONS.NAME IS 'Unique integration name';
COMMENT ON COLUMN INTEGRATIONS.BASE_URL IS 'Base URL of the remote platform';
COMMENT ON COLUMN INTEGRATIONS.CREDENTIAL_REF IS 'Vault path or logical name for credentials (no secrets stored)';
COMMENT ON COLUMN INTEGRATIONS.ICON IS 'Icon identifier (preset name or URL)';
COMMENT ON COLUMN INTEGRATIONS.CREATED_AT IS 'Creation timestamp';
COMMENT ON COLUMN INTEGRATIONS.UPDATED_AT IS 'Last update timestamp';
