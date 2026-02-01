-- V029: Add composite index for audit log queries (Story 6.3, Task 1.4, NFR24)
-- Performance optimization for filtering by ENTITY_TYPE and sorting by TIMESTAMP
-- Supports queries like: WHERE ENTITY_TYPE = 'execution' ORDER BY TIMESTAMP DESC

CREATE INDEX IDX_AUDIT_LOG_ENTITY_TYPE_TIMESTAMP ON AUDIT_LOG(ENTITY_TYPE, TIMESTAMP DESC);
