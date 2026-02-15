-- V075: Sync integration_role for platform vs service (Story 29.1)
-- Ensures correct role for all types (handles DBs where V072 UPDATE ran on empty table,
-- or where fixtures/seed loaded before integration_role existed)

-- Services: consumed by actions (Vault, ServiceNow, Jira, Splunk)
UPDATE INTEGRATION_TYPE_CATALOGUE
SET INTEGRATION_ROLE = 'service'
WHERE CODE IN ('vault', 'servicenow', 'jira', 'splunk')
  AND (INTEGRATION_ROLE IS NULL OR INTEGRATION_ROLE != 'service');

-- Platforms: where actions execute (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud)
UPDATE INTEGRATION_TYPE_CATALOGUE
SET INTEGRATION_ROLE = 'platform'
WHERE CODE IN ('aap', 'tower', 'azure_devops', 'github_actions', 'terraform_cloud')
  AND (INTEGRATION_ROLE IS NULL OR INTEGRATION_ROLE != 'platform');
