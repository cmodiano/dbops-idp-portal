-- Story 25.6: Add exclusion_patterns to PROFILE_TARGET_PERMISSIONS
-- Enables explicit deny patterns for RBAC (e.g., "all except PROD-CRITICAL-*")
-- Semantics: "allow first, then exclude"

ALTER TABLE PROFILE_TARGET_PERMISSIONS
ADD EXCLUSION_PATTERNS_JSON CLOB;

COMMENT ON COLUMN PROFILE_TARGET_PERMISSIONS.EXCLUSION_PATTERNS_JSON IS 'JSON array of patterns to exclude from allowed targets. Applied after inclusion rules. Format: ["PROD-CRITICAL-*", "DR-*"]. Story 25.6';
