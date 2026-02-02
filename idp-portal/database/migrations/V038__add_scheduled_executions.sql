-- V038: Create SCHEDULED_EXECUTIONS and RECURRING_PATTERNS tables
-- Story 11.1 - Modèle de données scheduled executions et récurrence
-- Epic 11 - Scheduling & Maintenance Planifiée (Phase 2)
--
-- Purpose: Store scheduled executions (one-time or recurring) for external scheduler
-- Approach: No internal scheduler (Celery) - external scheduler (Control-M/Django) queries NEXT_EXECUTION_DATE

-- ============================================================================
-- SCHEDULED_EXECUTIONS table - Base execution schedule information
-- ============================================================================
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = 'SCHEDULED_EXECUTIONS';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE '
            CREATE TABLE SCHEDULED_EXECUTIONS (
                ID NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                ACTION_ID NUMBER NOT NULL,
                USER_ID NUMBER NOT NULL,
                ENVIRONMENT VARCHAR2(50) NOT NULL,
                PARAMETERS CLOB,
                SCHEDULED_AT TIMESTAMP WITH TIME ZONE,
                STATUS VARCHAR2(20) DEFAULT ''pending'' NOT NULL,
                CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                UPDATED_AT TIMESTAMP WITH TIME ZONE,
                CONSTRAINT FK_SCHEDULED_EXEC_ACTION FOREIGN KEY (ACTION_ID) REFERENCES ACTIONS_CATALOG(ID),
                CONSTRAINT FK_SCHEDULED_EXEC_USER FOREIGN KEY (USER_ID) REFERENCES USERS(ID),
                CONSTRAINT CHK_SCHEDULED_ENV CHECK (ENVIRONMENT IN (''dev'', ''staging'', ''prod'')),
                CONSTRAINT CHK_SCHEDULED_STATUS CHECK (STATUS IN (''pending'', ''executed'', ''cancelled''))
            )
        ';

        -- Indexes for SCHEDULED_EXECUTIONS
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_SCHEDULED_EXEC_ACTION ON SCHEDULED_EXECUTIONS(ACTION_ID)';
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_SCHEDULED_EXEC_USER ON SCHEDULED_EXECUTIONS(USER_ID)';
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_SCHEDULED_EXEC_STATUS ON SCHEDULED_EXECUTIONS(STATUS)';

        -- Table comment
        EXECUTE IMMEDIATE 'COMMENT ON TABLE SCHEDULED_EXECUTIONS IS ''Exécutions planifiées (one-time ou recurring) pour le scheduler externe (Epic 11, Story 11.1)''';

        -- Column comments
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.ID IS ''Primary key, auto-generated identity''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.ACTION_ID IS ''FK to ACTIONS_CATALOG - the action to be executed''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.USER_ID IS ''FK to USERS - the user who created this scheduled execution''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.ENVIRONMENT IS ''Target environment: dev, staging, prod''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.PARAMETERS IS ''JSON parameters for the execution, validated against action parameters_schema''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.SCHEDULED_AT IS ''For one-time executions: the specific date/time to execute. For recurring: can be NULL (use RECURRING_PATTERNS.NEXT_EXECUTION_DATE)''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.STATUS IS ''Schedule status: pending (waiting), executed (completed), cancelled (user cancelled)''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.CREATED_AT IS ''Timestamp when schedule was created''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN SCHEDULED_EXECUTIONS.UPDATED_AT IS ''Timestamp when schedule was last modified''';
    END IF;
END;
/

-- ============================================================================
-- RECURRING_PATTERNS table - Recurrence configuration for scheduled executions
-- ============================================================================
DECLARE
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM user_tables WHERE table_name = 'RECURRING_PATTERNS';
    IF v_count = 0 THEN
        EXECUTE IMMEDIATE '
            CREATE TABLE RECURRING_PATTERNS (
                ID NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                SCHEDULED_EXECUTION_ID NUMBER NOT NULL,
                PATTERN_TYPE VARCHAR2(50) NOT NULL,
                PATTERN_CONFIG CLOB,
                NEXT_EXECUTION_DATE TIMESTAMP WITH TIME ZONE NOT NULL,
                IS_ACTIVE NUMBER(1) DEFAULT 1 NOT NULL,
                CREATED_AT TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
                UPDATED_AT TIMESTAMP WITH TIME ZONE,
                CONSTRAINT FK_RECURRING_PATTERN_SCHED_EXEC FOREIGN KEY (SCHEDULED_EXECUTION_ID) REFERENCES SCHEDULED_EXECUTIONS(ID) ON DELETE CASCADE,
                CONSTRAINT CHK_RECURRING_PATTERN_TYPE CHECK (PATTERN_TYPE IN (''one_time'', ''daily'', ''weekly'', ''cron'')),
                CONSTRAINT CHK_RECURRING_IS_ACTIVE CHECK (IS_ACTIVE IN (0, 1)),
                CONSTRAINT UNQ_RECURRING_SCHED_EXEC UNIQUE (SCHEDULED_EXECUTION_ID)
            )
        ';

        -- Indexes for RECURRING_PATTERNS
        -- Critical index for external scheduler query (AC6)
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_RECURRING_NEXT_EXEC ON RECURRING_PATTERNS(NEXT_EXECUTION_DATE)';
        -- Composite filtered index for active patterns (AC3) - optimized for scheduler query
        -- Note: Oracle syntax requires function-based index for WHERE clause simulation
        -- Using composite index (IS_ACTIVE, NEXT_EXECUTION_DATE) provides same performance benefit
        -- as partial index WHERE IS_ACTIVE = 1 (Oracle will use index skip scan for IS_ACTIVE = 1 predicate)
        EXECUTE IMMEDIATE 'CREATE INDEX IDX_RECURRING_ACTIVE_PENDING ON RECURRING_PATTERNS(IS_ACTIVE, NEXT_EXECUTION_DATE)';

        -- Table comment
        EXECUTE IMMEDIATE 'COMMENT ON TABLE RECURRING_PATTERNS IS ''Patterns de récurrence pour SCHEDULED_EXECUTIONS. Relation 1:0..1 - une exécution planifiée a au plus un pattern de récurrence (Epic 11, Story 11.1)''';

        -- Column comments
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.ID IS ''Primary key, auto-generated identity''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.SCHEDULED_EXECUTION_ID IS ''FK to SCHEDULED_EXECUTIONS - unique constraint ensures 1:0..1 relationship''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.PATTERN_TYPE IS ''Type de récurrence: one_time (exécution unique), daily (tous les jours), weekly (hebdomadaire), cron (expression cron)''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.PATTERN_CONFIG IS ''Configuration JSON du pattern. Exemples complets par PATTERN_TYPE: daily={"hour":2,"minute":30} (tous les jours à 2h30), weekly={"day_of_week":1,"hour":2,"minute":30} (lundis à 2h30, 1=lundi 7=dimanche), cron={"expression":"0 2 * * *"} (expression cron standard), one_time=null ou {} (exécution unique)''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.NEXT_EXECUTION_DATE IS ''Date calculée de la prochaine exécution - utilisée par le scheduler externe pour récupérer les jobs à lancer. Mis à jour après chaque exécution pour recurring patterns''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.IS_ACTIVE IS ''Boolean (1=actif, 0=inactif). Permet de désactiver un pattern sans le supprimer''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.CREATED_AT IS ''Timestamp when pattern was created''';
        EXECUTE IMMEDIATE 'COMMENT ON COLUMN RECURRING_PATTERNS.UPDATED_AT IS ''Timestamp when pattern was last modified''';
    END IF;
END;
/
