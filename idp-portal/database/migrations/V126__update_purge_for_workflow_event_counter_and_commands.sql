-- V126: Update purge_executions to delete from WORKFLOW_EVENT_COUNTER, WORKFLOW_COMMANDS,
-- and EXECUTION_OUTBOX before dropping EXECUTIONS partitions. Without these deletes,
-- partition drops fail with FK violation once any rows exist (ON DELETE CASCADE does
-- not trigger on DROP PARTITION). Aligns with WORKFLOW_EVENTS and RUNNABLE_STEPS.

CREATE OR REPLACE PACKAGE BODY PKG_IDP_MAINTENANCE AS

    PROCEDURE log_maintenance(
        p_table_name     IN VARCHAR2,
        p_partition_name IN VARCHAR2,
        p_action         IN VARCHAR2,
        p_status         IN VARCHAR2,
        p_dry_run        IN NUMBER,
        p_notes          IN VARCHAR2 DEFAULT NULL
    ) IS
    BEGIN
        INSERT INTO IDP_MAINTENANCE_LOG
            (TABLE_NAME, PARTITION_NAME, ACTION, STATUS, DRY_RUN, NOTES)
        VALUES
            (p_table_name, p_partition_name, p_action, p_status, p_dry_run, p_notes);
    EXCEPTION
        WHEN OTHERS THEN
            DBMS_OUTPUT.PUT_LINE(
                'WARNING: log_maintenance insert failed for '
                || p_table_name || '/' || p_partition_name
                || ' — ' || SQLERRM
            );
            RAISE;
    END log_maintenance;

    FUNCTION get_partition_date(p_high_value IN VARCHAR2) RETURN DATE IS
        v_date DATE;
    BEGIN
        EXECUTE IMMEDIATE 'SELECT ' || p_high_value || ' FROM DUAL' INTO v_date;
        RETURN v_date;
    EXCEPTION
        WHEN OTHERS THEN
            RETURN NULL;
    END get_partition_date;

    PROCEDURE purge_executions(
        p_retention_months  IN NUMBER  DEFAULT 24,
        p_dry_run           IN NUMBER  DEFAULT 1
    ) IS
        v_cutoff_date   DATE;
        v_part_date     DATE;
        v_rows_estimate NUMBER;
    BEGIN
        IF p_retention_months IS NULL OR p_retention_months < 1 OR p_retention_months > 600 THEN
            RAISE_APPLICATION_ERROR(-20001, 'purge_executions: p_retention_months must be between 1 and 600, got ' || NVL(TO_CHAR(p_retention_months), 'NULL'));
        END IF;
        IF p_dry_run NOT IN (0, 1) THEN
            RAISE_APPLICATION_ERROR(-20002, 'purge_executions: p_dry_run must be 0 or 1, got ' || NVL(TO_CHAR(p_dry_run), 'NULL'));
        END IF;

        v_cutoff_date := ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -p_retention_months);

        FOR r IN (
            SELECT PARTITION_NAME, HIGH_VALUE
            FROM   USER_TAB_PARTITIONS
            WHERE  TABLE_NAME = 'EXECUTIONS'
            AND    PARTITION_NAME != 'P_BEFORE_2024'
            ORDER BY PARTITION_POSITION
        ) LOOP
            v_part_date := get_partition_date(r.HIGH_VALUE);

            IF v_part_date IS NULL THEN
                log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'SKIP', 'SKIPPED',
                    p_dry_run, 'HIGH_VALUE non convertible: ' || SUBSTR(r.HIGH_VALUE, 1, 100));
                CONTINUE;
            END IF;

            IF v_part_date <= v_cutoff_date THEN
                IF p_dry_run = 0 THEN
                    EXECUTE IMMEDIATE
                        'DELETE FROM WORKFLOW_EVENTS WHERE EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_DELETE',
                        'SUCCESS', 0, 'WORKFLOW_EVENTS supprimés: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'DELETE FROM RUNNABLE_STEPS WHERE EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_DELETE',
                        'SUCCESS', 0, 'RUNNABLE_STEPS supprimés: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'DELETE FROM WORKFLOW_EVENT_COUNTER WHERE EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_DELETE',
                        'SUCCESS', 0, 'WORKFLOW_EVENT_COUNTER supprimés: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'DELETE FROM WORKFLOW_COMMANDS WHERE EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_DELETE',
                        'SUCCESS', 0, 'WORKFLOW_COMMANDS supprimés: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'DELETE FROM EXECUTION_OUTBOX WHERE EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_DELETE',
                        'SUCCESS', 0, 'EXECUTION_OUTBOX supprimés: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'UPDATE SCHEDULED_EXECUTIONS SET SOURCE_EXECUTION_ID = NULL '
                        || 'WHERE SOURCE_EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_UPDATE',
                        'SUCCESS', 0, 'SCHEDULED_EXECUTIONS SOURCE_EXECUTION_ID nullifiés: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'UPDATE EXECUTIONS SET PARENT_EXECUTION_ID = NULL '
                        || 'WHERE PARENT_EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_UPDATE',
                        'SUCCESS', 0, 'PARENT_EXECUTION_ID nullified: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'DELETE FROM EXECUTION_TARGETS '
                        || 'WHERE EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_DELETE',
                        'SUCCESS', 0, 'EXECUTION_TARGETS orphelins supprimés: ' || SQL%ROWCOUNT || ' rows');

                    EXECUTE IMMEDIATE
                        'UPDATE SCHEDULED_EXECUTIONS SET EXECUTION_ID = NULL '
                        || 'WHERE EXECUTION_ID IN '
                        || '(SELECT ID FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || '))';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'PREREQ_UPDATE',
                        'SUCCESS', 0, 'SCHEDULED_EXECUTIONS EXECUTION_ID détachés: ' || SQL%ROWCOUNT || ' rows');

                    COMMIT;

                    EXECUTE IMMEDIATE
                        'ALTER TABLE EXECUTIONS DROP PARTITION ' || r.PARTITION_NAME
                        || ' UPDATE GLOBAL INDEXES';

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'DROP', 'SUCCESS', 0,
                        'EXECUTION_STEPS cascade automatique (Reference Partitioning V085)');
                ELSE
                    BEGIN
                        EXECUTE IMMEDIATE
                            'SELECT COUNT(*) FROM EXECUTIONS PARTITION (' || r.PARTITION_NAME || ')'
                            INTO v_rows_estimate;
                    EXCEPTION
                        WHEN OTHERS THEN v_rows_estimate := -1;
                    END;

                    log_maintenance('EXECUTIONS', r.PARTITION_NAME, 'DROP', 'DRY_RUN', 1,
                        'Estimated rows: ' || v_rows_estimate
                        || ' | HIGH_VALUE: ' || TO_CHAR(v_part_date, 'YYYY-MM-DD'));
                END IF;
            END IF;
        END LOOP;

        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END purge_executions;

    PROCEDURE purge_audit_log(
        p_retention_months  IN NUMBER  DEFAULT 12,
        p_dry_run           IN NUMBER  DEFAULT 1
    ) IS
        v_cutoff_date   DATE;
        v_part_date     DATE;
        v_rows_estimate NUMBER;
    BEGIN
        IF p_retention_months IS NULL OR p_retention_months < 1 OR p_retention_months > 600 THEN
            RAISE_APPLICATION_ERROR(-20003, 'purge_audit_log: p_retention_months must be between 1 and 600, got ' || NVL(TO_CHAR(p_retention_months), 'NULL'));
        END IF;
        IF p_dry_run NOT IN (0, 1) THEN
            RAISE_APPLICATION_ERROR(-20004, 'purge_audit_log: p_dry_run must be 0 or 1, got ' || NVL(TO_CHAR(p_dry_run), 'NULL'));
        END IF;

        v_cutoff_date := ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -p_retention_months);

        FOR r IN (
            SELECT PARTITION_NAME, HIGH_VALUE
            FROM   USER_TAB_PARTITIONS
            WHERE  TABLE_NAME = 'AUDIT_LOG'
            AND    PARTITION_NAME != 'P_INITIAL'
            ORDER BY PARTITION_POSITION
        ) LOOP
            v_part_date := get_partition_date(r.HIGH_VALUE);

            IF v_part_date IS NULL THEN
                log_maintenance('AUDIT_LOG', r.PARTITION_NAME, 'SKIP', 'SKIPPED',
                    p_dry_run, 'HIGH_VALUE non convertible: ' || SUBSTR(r.HIGH_VALUE, 1, 100));
                CONTINUE;
            END IF;

            IF v_part_date <= v_cutoff_date THEN
                IF p_dry_run = 0 THEN
                    EXECUTE IMMEDIATE
                        'ALTER TABLE AUDIT_LOG DROP PARTITION ' || r.PARTITION_NAME
                        || ' UPDATE GLOBAL INDEXES';

                    log_maintenance('AUDIT_LOG', r.PARTITION_NAME, 'DROP', 'SUCCESS', 0, NULL);
                ELSE
                    BEGIN
                        EXECUTE IMMEDIATE
                            'SELECT COUNT(*) FROM AUDIT_LOG PARTITION (' || r.PARTITION_NAME || ')'
                            INTO v_rows_estimate;
                    EXCEPTION
                        WHEN OTHERS THEN v_rows_estimate := -1;
                    END;

                    log_maintenance('AUDIT_LOG', r.PARTITION_NAME, 'DROP', 'DRY_RUN', 1,
                        'Estimated rows: ' || v_rows_estimate
                        || ' | HIGH_VALUE: ' || TO_CHAR(v_part_date, 'YYYY-MM-DD'));
                END IF;
            END IF;
        END LOOP;

        COMMIT;
    EXCEPTION
        WHEN OTHERS THEN
            ROLLBACK;
            RAISE;
    END purge_audit_log;

    PROCEDURE purge_old_partitions(
        p_retention_executions  IN NUMBER  DEFAULT 24,
        p_retention_audit_log   IN NUMBER  DEFAULT 12,
        p_dry_run               IN NUMBER  DEFAULT 1
    ) IS
    BEGIN
        purge_executions(
            p_retention_months => p_retention_executions,
            p_dry_run          => p_dry_run
        );

        purge_audit_log(
            p_retention_months => p_retention_audit_log,
            p_dry_run          => p_dry_run
        );
    END purge_old_partitions;

END PKG_IDP_MAINTENANCE;
/
