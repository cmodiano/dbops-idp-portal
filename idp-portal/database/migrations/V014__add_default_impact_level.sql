-- V014: Add DEFAULT_IMPACT_LEVEL column to ACTIONS_CATALOG
-- Story 2.18 AC5 - Niveau d'impact par defaut quand aucune regle ne correspond a l'environnement
-- Review fix: Backend ne persistait pas ce champ

-- Add column for default impact level (nullable, applies when no rule matches environment)
ALTER TABLE ACTIONS_CATALOG ADD (
    DEFAULT_IMPACT_LEVEL VARCHAR2(20)
);

-- Constraint: valid impact levels only
ALTER TABLE ACTIONS_CATALOG ADD CONSTRAINT CK_ACTIONS_CATALOG_DEF_IMPACT
    CHECK (DEFAULT_IMPACT_LEVEL IS NULL OR DEFAULT_IMPACT_LEVEL IN ('low', 'medium', 'high', 'critical'));

-- Column comment
COMMENT ON COLUMN ACTIONS_CATALOG.DEFAULT_IMPACT_LEVEL IS 'Default impact level when no impact_rule matches the execution environment. Valid values: low, medium, high, critical. Nullable.';
