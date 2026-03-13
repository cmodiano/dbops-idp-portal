-- V125: Add EXECUTION_OUTBOX table for transactional outbox pattern (Story 78.7)
-- Persists side-effects (notifications, websocket broadcast, event emission)
-- in the same transaction as the business mutation, enabling reliable at-least-once delivery.

CREATE TABLE EXECUTION_OUTBOX (
    ID              NUMBER(19) GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    EXECUTION_ID    NUMBER(19) NOT NULL REFERENCES EXECUTIONS(ID),
    EVENT_TYPE      VARCHAR2(50) NOT NULL,
    PAYLOAD         CLOB CHECK (PAYLOAD IS JSON),
    STATUS          VARCHAR2(20) DEFAULT 'pending' NOT NULL,
    IDEMPOTENCY_KEY VARCHAR2(255) NOT NULL UNIQUE,
    CREATED_AT      TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    DISPATCHED_AT   TIMESTAMP,
    ATTEMPT_NO      NUMBER(10) DEFAULT 0 NOT NULL,
    MAX_ATTEMPTS    NUMBER(10) DEFAULT 3 NOT NULL,
    LAST_ERROR      CLOB
);

CREATE INDEX idx_outbox_status_created ON EXECUTION_OUTBOX (STATUS, CREATED_AT);
