-- V055: Extend workflow steps schema to support branches and retry
-- Story 16.2: Modèle de données pour workflows avec branches et retry
-- AC1-AC5: Add branch conditional and retry fields to workflow steps JSON schema

-- Note: No structural table changes required.
-- The ACTIONS_CATALOG.EXECUTION_STEPS CLOB already stores workflow steps as JSON.
-- This migration documents the extended JSON schema format.

-- Extended JSON schema for workflow steps (stored in ACTIONS_CATALOG.EXECUTION_STEPS):
-- For workflows (ITEM_TYPE='workflow'):
-- [
--   {
--     "order": 1,
--     "name": "Step name",
--     "referenced_action_id": 42,
--     "step_id": "unique-step-id",              -- NEW: stable ID for referencing
--     "on_success_step_id": "next-step-id",     -- NEW: next step on success (nullable)
--     "on_error_step_id": "error-step-id",      -- NEW: next step on error (nullable)
--     "retry_enabled": false,                   -- NEW: enable retry for this step
--     "retry_max_attempts": 3,                  -- NEW: max retry attempts (nullable, default: 3)
--     "retry_interval_seconds": 60,             -- NEW: seconds between retries (nullable, default: 60)
--     "retry_backoff_multiplier": 2.0           -- NEW: backoff multiplier (nullable, default: 2.0)
--   }
-- ]

-- Validation rules (enforced in application layer - catalog/serializers.py):
-- 1. All on_success_step_id and on_error_step_id must reference valid step_id in same workflow
-- 2. No infinite loops in branch paths (DFS/BFS cycle detection)
-- 3. At least one step must have on_success_step_id=null OR on_error_step_id=null (exit point)
-- 4. If retry_enabled=true, then retry_max_attempts >= 1
-- 5. If retry_enabled=true, then retry_interval_seconds >= 1
-- 6. Backward compatibility: workflows without branch/retry fields continue to work (linear flow by order)

COMMENT ON COLUMN ACTIONS_CATALOG.EXECUTION_STEPS IS 'JSON CLOB storing execution steps. For workflows (ITEM_TYPE=workflow): includes step_id, on_success_step_id, on_error_step_id, retry_enabled, retry_max_attempts, retry_interval_seconds, retry_backoff_multiplier for branch conditional logic and retry behavior (Story 16.2)';

-- No data migration needed - existing workflows remain valid (linear flow preserved by order field)
