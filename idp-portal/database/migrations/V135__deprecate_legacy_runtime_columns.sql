-- V135: Deprecate legacy runtime approval columns on EXECUTIONS (Story 78.14, ADR-007)
-- Marks APPROVED_BY, APPROVED_AT, APPROVAL_COMMENT as deprecated via COMMENT ON COLUMN.
-- Removes PENDING_APPROVAL from CHK_EXECUTION_STATUS CHECK constraint.
-- No columns are dropped — that is Story 78.15.

-- 1. COMMENT ON COLUMN: mark deprecated columns
COMMENT ON COLUMN EXECUTIONS.APPROVED_BY IS 'DEPRECATED (Story 78.14, ADR-007) — Source of truth: EXECUTION_STEPS.APPROVED_BY. Suppression prévue Story 78.15.';
COMMENT ON COLUMN EXECUTIONS.APPROVED_AT IS 'DEPRECATED (Story 78.14, ADR-007) — Source of truth: EXECUTION_STEPS.APPROVED_AT. Suppression prévue Story 78.15.';
COMMENT ON COLUMN EXECUTIONS.APPROVAL_COMMENT IS 'DEPRECATED (Story 78.14, ADR-007) — Source of truth: EXECUTION_STEPS.APPROVAL_COMMENT. Suppression prévue Story 78.15.';

-- 2. Migrate any PENDING_APPROVAL rows to SUBMITTED (safety net — should be 0 rows)
DECLARE
  v_count NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count FROM EXECUTIONS WHERE STATUS = 'PENDING_APPROVAL';
  IF v_count > 0 THEN
    UPDATE EXECUTIONS SET STATUS = 'SUBMITTED' WHERE STATUS = 'PENDING_APPROVAL';
    DBMS_OUTPUT.PUT_LINE('Migrated ' || v_count || ' PENDING_APPROVAL rows to SUBMITTED');
  END IF;
END;
/

-- 3. Replace CHECK constraint without PENDING_APPROVAL (idempotent)
-- Step 3a: Drop existing constraint (ignore if already dropped)
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS DROP CONSTRAINT CHK_EXECUTION_STATUS';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -2443 THEN NULL; -- ORA-02443: constraint does not exist
    ELSE RAISE;
    END IF;
END;
/

-- Step 3b: Re-create constraint without PENDING_APPROVAL (ignore if already exists)
BEGIN
  EXECUTE IMMEDIATE 'ALTER TABLE EXECUTIONS ADD CONSTRAINT CHK_EXECUTION_STATUS CHECK (STATUS IN (
    ''SUBMITTED'', ''INTEGRATION_ERROR'',
    ''RUNNING'', ''COMPLETED'', ''FAILED'', ''CANCELLED'', ''REJECTED''
  ))';
EXCEPTION
  WHEN OTHERS THEN
    IF SQLCODE = -2264 THEN NULL; -- ORA-02264: name already used by an existing constraint
    ELSE RAISE;
    END IF;
END;
/
