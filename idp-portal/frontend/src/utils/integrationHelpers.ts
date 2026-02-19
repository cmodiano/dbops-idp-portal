/**
 * Integration helper utilities (Story 31.1).
 * Maps integration types to platform codes and connector types.
 */

import type { ActionPlatform, ConnectorType } from '../types/api';

/**
 * Map integration type code to the platform code recognized by the backend (REF_PLATFORMS).
 * Fallback: returns the type as-is if no explicit mapping exists.
 */
const INTEGRATION_TYPE_TO_PLATFORM: Record<string, ActionPlatform> = {
  aap: 'AAP',
  tower: 'Tower',
  github_actions: 'GitHub Actions',
  azure_devops: 'Azure DevOps',
  terraform: 'Terraform',
  terraform_cloud: 'Terraform',
};

export function integrationTypeToPlatformCode(type: string): ActionPlatform | string {
  return INTEGRATION_TYPE_TO_PLATFORM[type] ?? type;
}

/**
 * Derive connector type from integration type (replaces platformToConnector).
 */
const INTEGRATION_TYPE_TO_CONNECTOR: Record<string, ConnectorType> = {
  aap: 'aap',
  tower: 'aap',
  github_actions: 'github_actions',
  azure_devops: 'azuredevops',
  terraform: 'terraform',
  terraform_cloud: 'terraform',
};

export function integrationToConnector(integrationType: string): ConnectorType {
  return INTEGRATION_TYPE_TO_CONNECTOR[integrationType] ?? 'none';
}
