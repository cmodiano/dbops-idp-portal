-- =============================================================================
-- DBOPS_INVENTORY Schema — Design correct
-- =============================================================================
-- Relations:
--   INSTANCE.SERVER_ID → SERVER.ID
--   INSTANCE.DB_ID     → DB.ID
--
-- INSTANCE is the junction table linking servers to databases.
-- One instance = one server + one database (e.g. Oracle instance on a host).
--
-- Usage:
--   1. Create schema: CREATE USER DBOPS_INVENTORY IDENTIFIED BY <pwd> QUOTA UNLIMITED ON USERS; GRANT CONNECT, RESOURCE TO DBOPS_INVENTORY;
--   2. Connect as DBOPS_INVENTORY and run this script.
--   3. Run seed_dboss_inventory_server.sql
-- =============================================================================

-- -----------------------------------------------------------------------------
-- SERVER — Physical hosts
-- -----------------------------------------------------------------------------
CREATE TABLE SERVER (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    NAME            VARCHAR2(255) NOT NULL,
    HOSTNAME        VARCHAR2(512) NOT NULL,
    IP_ADDRESS      VARCHAR2(45),
    ENVIRONMENT     VARCHAR2(50) NOT NULL,
    OS_TYPE         VARCHAR2(50),
    ENGINE_TYPE     VARCHAR2(50),
    STATUS          VARCHAR2(20) DEFAULT 'ACTIVE',
    ENABLED         CHAR(1) DEFAULT 'Y',
    LOCATION        VARCHAR2(255),
    CREATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    UPDATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    CREATED_BY      VARCHAR2(255),
    UPDATED_BY      VARCHAR2(255),
    CONSTRAINT UK_SERVER_NAME UNIQUE (NAME),
    CONSTRAINT CK_SERVER_ENABLED CHECK (ENABLED IN ('Y', 'N'))
);

CREATE INDEX IDX_SERVER_ENVIRONMENT ON SERVER(ENVIRONMENT);
CREATE INDEX IDX_SERVER_ENABLED ON SERVER(ENABLED);

COMMENT ON TABLE SERVER IS 'Physical hosts. Environment: DEV, STAGING, PROD.';
COMMENT ON COLUMN SERVER.ENGINE_TYPE IS 'DB engine (oracle, sql_server, etc.) for InventoryMapper engine_type.';

-- -----------------------------------------------------------------------------
-- DB — Databases (logical, independent of host)
-- -----------------------------------------------------------------------------
CREATE TABLE DB (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    NAME            VARCHAR2(255) NOT NULL,
    DB_UNIQUE_NAME  VARCHAR2(255),
    DB_TYPE         VARCHAR2(50),
    VERSION         VARCHAR2(50),
    STATUS          VARCHAR2(20) DEFAULT 'ACTIVE',
    CREATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    UPDATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    CONSTRAINT UK_DB_NAME UNIQUE (NAME)
);

CREATE INDEX IDX_DB_STATUS ON DB(STATUS);

COMMENT ON TABLE DB IS 'Logical databases. Linked to servers via INSTANCE.';

-- -----------------------------------------------------------------------------
-- INSTANCE — Junction: server + database
-- -----------------------------------------------------------------------------
CREATE TABLE INSTANCE (
    ID              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    SERVER_ID       NUMBER NOT NULL,
    DB_ID           NUMBER NOT NULL,
    NAME            VARCHAR2(255) NOT NULL,
    ORACLE_HOME     VARCHAR2(1000),
    ORACLE_VERSION  VARCHAR2(50),
    SID             VARCHAR2(64),
    PORT            NUMBER,
    STATUS          VARCHAR2(20) DEFAULT 'ACTIVE',
    CREATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    UPDATED_AT      TIMESTAMP DEFAULT TO_TIMESTAMP(TO_CHAR(SYSTIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS.FF6'), 'YYYY-MM-DD HH24:MI:SS.FF6') NOT NULL,
    CONSTRAINT FK_INSTANCE_SERVER FOREIGN KEY (SERVER_ID) REFERENCES SERVER(ID) ON DELETE CASCADE,
    CONSTRAINT FK_INSTANCE_DB     FOREIGN KEY (DB_ID)     REFERENCES DB(ID) ON DELETE CASCADE,
    CONSTRAINT UK_INSTANCE_SERVER_DB UNIQUE (SERVER_ID, DB_ID)
);

CREATE INDEX IDX_INSTANCE_SERVER ON INSTANCE(SERVER_ID);
CREATE INDEX IDX_INSTANCE_DB ON INSTANCE(DB_ID);

COMMENT ON TABLE INSTANCE IS 'Instance = server + database. Links SERVER to DB.';

-- InventoryMapper config uses ref_join: "id" so server_ref→SERVER_ID, db_ref→DB_ID.
-- No view needed: joins use inst.SERVER_ID = srv.ID and inst.DB_ID = d.ID.
