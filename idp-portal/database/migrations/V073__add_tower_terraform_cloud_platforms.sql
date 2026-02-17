-- V073: Add missing platforms to REF_PLATFORMS (Story 29.4)
-- Align REF_PLATFORMS with IntegrationTypeCatalogue platform types
-- Gap: Tower and Terraform Cloud present in IntegrationTypeCatalogue but missing from REF_PLATFORMS

-- Add Tower (Ansible Tower - predecessor of AAP) - idempotent insert
INSERT INTO REF_PLATFORMS (CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE)
SELECT 'Tower', 'Ansible Tower', 5, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM REF_PLATFORMS WHERE CODE = 'Tower');

-- Add Terraform Cloud (specific platform, distinct from generic Terraform) - idempotent insert
INSERT INTO REF_PLATFORMS (CODE, LABEL, DISPLAY_ORDER, IS_ACTIVE)
SELECT 'Terraform Cloud', 'Terraform Cloud', 6, 1 FROM DUAL
WHERE NOT EXISTS (SELECT 1 FROM REF_PLATFORMS WHERE CODE = 'Terraform Cloud');

COMMENT ON TABLE REF_PLATFORMS IS 'Reference table for execution platforms. Story 29.4: Aligned with IntegrationTypeCatalogue platform types for consistency validation.';
