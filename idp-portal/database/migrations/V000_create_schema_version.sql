-- V000: Create SCHEMA_VERSION table for migration tracking.
-- Used by migration runner; each migration (V001, V002, ...) records its version here.

CREATE TABLE SCHEMA_VERSION (
    VERSION   VARCHAR2(20) PRIMARY KEY,
    APPLIED_AT TIMESTAMP DEFAULT SYSTIMESTAMP NOT NULL
);
