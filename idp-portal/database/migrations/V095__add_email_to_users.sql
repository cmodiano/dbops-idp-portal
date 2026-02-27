-- V095: Add EMAIL column to USERS table
-- Story 50.1 - Email utilisateur depuis AD

ALTER TABLE USERS ADD (EMAIL VARCHAR2(254));
