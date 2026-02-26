-- Create application user idp_app in PDB FREEPDB1 (Oracle Free image).
-- Used by run_migrations.sh and backend config (oracle_user=idp_app).
-- Runs on container startup via /opt/oracle/scripts/startup.

ALTER SESSION SET CONTAINER = FREEPDB1;

CREATE USER idp_app IDENTIFIED BY "Oracle123!"
  QUOTA UNLIMITED ON USERS;

GRANT CONNECT, RESOURCE TO idp_app;
