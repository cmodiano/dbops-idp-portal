-- V060: Add FILTER_BY_ATTRIBUTE_JSON to PROFILE_TARGET_PERMISSIONS
-- Story 23.4 - RBAC filter by inventory attributes (engine_type, zone, etc.)
-- Format: JSON dict mapping concept keys to value lists, e.g. {"engine_type": ["oracle"], "zone": ["prod"]}

ALTER TABLE PROFILE_TARGET_PERMISSIONS ADD FILTER_BY_ATTRIBUTE_JSON CLOB;

COMMENT ON COLUMN PROFILE_TARGET_PERMISSIONS.FILTER_BY_ATTRIBUTE_JSON IS 'JSON dict filtering targets by inventory attributes. Keys = business concepts from InventoryMapper (e.g. engine_type, zone). Example: {"engine_type": ["oracle","sqlserver"], "zone": ["prod"]}';
