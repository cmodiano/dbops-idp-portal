-- V015: Drop custom SCHEMA_VERSION table (Story 2.20 - Flyway native)
-- Flyway uses flyway_schema_history; no migration shall write to SCHEMA_VERSION anymore.

DROP TABLE SCHEMA_VERSION;
