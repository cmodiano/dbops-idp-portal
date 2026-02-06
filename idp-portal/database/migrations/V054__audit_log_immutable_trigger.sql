-- V054: Enforce AUDIT_LOG immutability at database level (SOC1/NFR8)
-- Trigger prevents UPDATE and DELETE operations on AUDIT_LOG table.
-- Defense in depth: application layer also blocks these via Django model overrides.

CREATE OR REPLACE TRIGGER TRG_AUDIT_LOG_IMMUTABLE
BEFORE UPDATE OR DELETE ON AUDIT_LOG
FOR EACH ROW
BEGIN
    RAISE_APPLICATION_ERROR(-20001, 'AUDIT_LOG is immutable - UPDATE and DELETE operations are forbidden (SOC1/NFR8)');
END;
/
