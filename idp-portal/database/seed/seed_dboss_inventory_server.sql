-- =============================================================================
-- Seed: DBOPS_INVENTORY — SERVER, DB, INSTANCE
-- =============================================================================
-- Design: INSTANCE links SERVER (SERVER_ID) to DB (DB_ID).
-- Usage: Run after dbops_inventory_schema.sql in schema DBOPS_INVENTORY.
--
-- Cas d'usage portail: inventaire (Story 13.1), wizard exécution (13.2),
-- filtres par environnement (DEV, STAGING, PROD). Le portail normalise
-- certif/test → staging ; utiliser DEV, STAGING, PROD pour cohérence.
--
-- InventoryMapper config (schema=DBOPS_INVENTORY, ref_join: id for FK-based links):
--   servers: table SERVER, id_column ID, columns {name: NAME, environment: ENVIRONMENT, engine_type: ENGINE_TYPE}
--   instances: table INSTANCE, id_column ID, columns {name: NAME, server_ref: SERVER_ID, db_ref: DB_ID}, ref_join: "id"
--   databases: table DB, id_column ID, columns {name: NAME}
-- =============================================================================

-- Nettoyer les données de test (optionnel, décommenter si rejeu)
-- DELETE FROM DBOPS_INVENTORY.INSTANCE WHERE 1=1;
-- DELETE FROM DBOPS_INVENTORY.DB WHERE NAME LIKE 'db-%';
-- DELETE FROM DBOPS_INVENTORY.SERVER WHERE NAME LIKE 'srv-%';

-- -----------------------------------------------------------------------------
-- SERVER
-- -----------------------------------------------------------------------------
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-dev-01', 'srv-dev-01.entreprise.local', '10.10.1.11', 'DEV', 'Linux', 'oracle', 'ACTIVE', 'Y', 'DC1-Rack-A');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-dev-02', 'srv-dev-02.entreprise.local', '10.10.1.12', 'DEV', 'Linux', 'oracle', 'ACTIVE', 'Y', 'DC1-Rack-A');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-dev-03', 'srv-dev-03.entreprise.local', '10.10.1.13', 'DEV', 'Windows', 'sql_server', 'ACTIVE', 'Y', 'DC1-Rack-B');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-test-01', 'srv-test-01.entreprise.local', '10.20.1.21', 'STAGING', 'Linux', 'oracle', 'ACTIVE', 'Y', 'DC1-Rack-C');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-test-02', 'srv-test-02.entreprise.local', '10.20.1.22', 'STAGING', 'Linux', 'oracle', 'ACTIVE', 'Y', 'DC1-Rack-C');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-prod-01', 'srv-prod-01.entreprise.local', '10.30.1.31', 'PROD', 'Linux', 'oracle', 'ACTIVE', 'Y', 'DC2-Rack-A');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-prod-02', 'srv-prod-02.entreprise.local', '10.30.1.32', 'PROD', 'Linux', 'oracle', 'ACTIVE', 'Y', 'DC2-Rack-A');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-prod-03', 'srv-prod-03.entreprise.local', '10.30.1.33', 'PROD', 'Linux', 'oracle', 'ACTIVE', 'Y', 'DC2-Rack-B');
INSERT INTO DBOPS_INVENTORY.SERVER (NAME, HOSTNAME, IP_ADDRESS, ENVIRONMENT, OS_TYPE, ENGINE_TYPE, STATUS, ENABLED, LOCATION) VALUES
  ('srv-dev-off', 'srv-dev-off.entreprise.local', '10.10.1.99', 'DEV', 'Linux', 'oracle', 'ACTIVE', 'N', 'DC1-Rack-A');

-- -----------------------------------------------------------------------------
-- DB
-- -----------------------------------------------------------------------------
INSERT INTO DBOPS_INVENTORY.DB (NAME, DB_UNIQUE_NAME, DB_TYPE, VERSION, STATUS) VALUES
  ('db-dev-app', 'DBDEVAPP', 'Oracle', '19c', 'ACTIVE');
INSERT INTO DBOPS_INVENTORY.DB (NAME, DB_UNIQUE_NAME, DB_TYPE, VERSION, STATUS) VALUES
  ('db-dev-report', 'DBDEVREP', 'Oracle', '19c', 'ACTIVE');
INSERT INTO DBOPS_INVENTORY.DB (NAME, DB_UNIQUE_NAME, DB_TYPE, VERSION, STATUS) VALUES
  ('db-dev-mssql', 'DBDEVMS', 'SQL Server', '2019', 'ACTIVE');
INSERT INTO DBOPS_INVENTORY.DB (NAME, DB_UNIQUE_NAME, DB_TYPE, VERSION, STATUS) VALUES
  ('db-test-app', 'DBTESTAPP', 'Oracle', '19c', 'ACTIVE');
INSERT INTO DBOPS_INVENTORY.DB (NAME, DB_UNIQUE_NAME, DB_TYPE, VERSION, STATUS) VALUES
  ('db-prod-app', 'DBPRODAPP', 'Oracle', '19c', 'ACTIVE');
INSERT INTO DBOPS_INVENTORY.DB (NAME, DB_UNIQUE_NAME, DB_TYPE, VERSION, STATUS) VALUES
  ('db-prod-report', 'DBPRODREP', 'Oracle', '19c', 'ACTIVE');

-- -----------------------------------------------------------------------------
-- INSTANCE (SERVER_ID → SERVER, DB_ID → DB)
-- -----------------------------------------------------------------------------
-- srv-dev-01: 2 instances (app, report)
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-dev-01-app', 'ORCL', 1521, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-dev-01' AND d.NAME = 'db-dev-app';
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-dev-01-report', 'REP', 1522, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-dev-01' AND d.NAME = 'db-dev-report';

-- srv-dev-02: 1 instance
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-dev-02-app', 'ORCL', 1521, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-dev-02' AND d.NAME = 'db-dev-app';

-- srv-dev-03: SQL Server
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-dev-03-mssql', 1433, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-dev-03' AND d.NAME = 'db-dev-mssql';

-- srv-test-01, srv-test-02: staging
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-test-01-app', 'ORCL', 1521, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-test-01' AND d.NAME = 'db-test-app';
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-test-02-app', 'ORCL', 1521, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-test-02' AND d.NAME = 'db-test-app';

-- srv-prod-01, srv-prod-02, srv-prod-03: production
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-prod-01-app', 'ORCL', 1521, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-prod-01' AND d.NAME = 'db-prod-app';
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-prod-02-app', 'ORCL', 1521, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-prod-02' AND d.NAME = 'db-prod-app';
INSERT INTO DBOPS_INVENTORY.INSTANCE (SERVER_ID, DB_ID, NAME, SID, PORT, STATUS)
  SELECT s.ID, d.ID, 'inst-prod-03-report', 'REP', 1522, 'ACTIVE'
  FROM DBOPS_INVENTORY.SERVER s, DBOPS_INVENTORY.DB d WHERE s.NAME = 'srv-prod-03' AND d.NAME = 'db-prod-report';

COMMIT;

-- Vérification
-- SELECT s.NAME AS SERVER, i.NAME AS INSTANCE, d.NAME AS DB, s.ENVIRONMENT
-- FROM INSTANCE i
-- JOIN SERVER s ON i.SERVER_ID = s.ID
-- JOIN DB d ON i.DB_ID = d.ID
-- ORDER BY s.ENVIRONMENT, s.NAME, i.NAME;
