-- Create application user idp_app in PDB XEPDB1 (gvenzl/oracle-xe).
-- Used by run_migrations.sh and backend config (oracle_user=idp_app).
-- Runs once on first container startup via /container-entrypoint-initdb.d/.

ALTER SESSION SET CONTAINER = XEPDB1;

CREATE USER idp_app IDENTIFIED BY changeme
  QUOTA UNLIMITED ON USERS;

GRANT CONNECT, RESOURCE TO idp_app;
