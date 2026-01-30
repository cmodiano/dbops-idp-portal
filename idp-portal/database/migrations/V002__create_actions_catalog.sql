-- V002: Create ACTIONS_CATALOG table
-- Story 2.1 - Creer une action avec ses metadonnees
-- FR1: DBOPS peut creer une action dans le Software Catalog

-- Main catalog table (Story 2.20: identity column)
CREATE TABLE ACTIONS_CATALOG (
    ID                  NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    NAME                VARCHAR2(255) NOT NULL,
    DESCRIPTION         VARCHAR2(4000),
    CATEGORY            VARCHAR2(50) NOT NULL,
    ENGINE              VARCHAR2(50) NOT NULL,
    PLATFORM            VARCHAR2(50) NOT NULL,
    PARAMETERS_SCHEMA   CLOB,
    IMPACT_RULES        CLOB,
    RBAC_POLICIES       CLOB,
    STATUS              VARCHAR2(20) DEFAULT 'draft' NOT NULL,
    CREATED_BY          NUMBER,
    CREATED_AT          TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL,
    UPDATED_AT          TIMESTAMP,

    -- Constraints
    CONSTRAINT UK_ACTIONS_CATALOG_NAME UNIQUE (NAME),
    CONSTRAINT FK_ACTIONS_CATALOG_USER FOREIGN KEY (CREATED_BY) REFERENCES USERS(ID),
    CONSTRAINT CK_ACTIONS_CATALOG_CATEGORY CHECK (CATEGORY IN ('Provisioning', 'Patching', 'Administration', 'Monitoring')),
    CONSTRAINT CK_ACTIONS_CATALOG_ENGINE CHECK (ENGINE IN ('Oracle', 'SQL Server', 'DB2')),
    CONSTRAINT CK_ACTIONS_CATALOG_PLATFORM CHECK (PLATFORM IN ('AAP', 'GitHub Actions', 'Azure DevOps', 'Terraform')),
    CONSTRAINT CK_ACTIONS_CATALOG_STATUS CHECK (STATUS IN ('draft', 'published', 'disabled'))
);

-- Indexes for common queries
CREATE INDEX IDX_ACTIONS_CATALOG_STATUS ON ACTIONS_CATALOG(STATUS);
CREATE INDEX IDX_ACTIONS_CATALOG_CATEGORY ON ACTIONS_CATALOG(CATEGORY);
CREATE INDEX IDX_ACTIONS_CATALOG_ENGINE ON ACTIONS_CATALOG(ENGINE);

-- Column comments for JSON schema documentation
COMMENT ON COLUMN ACTIONS_CATALOG.PARAMETERS_SCHEMA IS 'JSON Schema (draft-07) defining action parameters. Example: {"$schema":"http://json-schema.org/draft-07/schema#","type":"object","properties":{"database_name":{"type":"string"}}}';
COMMENT ON COLUMN ACTIONS_CATALOG.IMPACT_RULES IS 'JSON object mapping environment to impact level. Example: {"DEV":{"level":"low"},"STAGING":{"level":"medium"},"PROD":{"level":"high"}}. Valid levels: low, medium, high, critical';
COMMENT ON COLUMN ACTIONS_CATALOG.RBAC_POLICIES IS 'JSON object defining RBAC rules per profile and environment. Example: {"DBA_APP":{"DEV":true,"PROD":false},"DBOPS":{"DEV":true,"PROD":true}}';
