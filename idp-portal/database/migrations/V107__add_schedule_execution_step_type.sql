-- Story 57.15/57.17: Add 'schedule_execution' to CHK_STEP_TYPE constraint
-- Without this, INSERT into EXECUTION_STEPS with step_type='schedule_execution' fails ORA-02290
-- Idempotent: DROP + ADD fonctionne que la contrainte vienne du baseline ou d'une migration antérieure
ALTER TABLE EXECUTION_STEPS DROP CONSTRAINT CHK_STEP_TYPE;
ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT CHK_STEP_TYPE
    CHECK (STEP_TYPE IN (
        'vault', 'servicenow', 'platform', 'prerequisite', 'verification',
        'service_call', 'http_request', 'evaluation', 'gate',
        'schedule_execution'
    ));
