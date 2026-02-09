// === Integration Types (Story 2.28, 4.9) ===

/** Story 4.9 AC1: Integration type is now free-form string (not enum).
 * Suggested types for UI autocomplete (legacy types, not enforced). */
/** Epic 13: inventory = API externe, inventory_db = schéma BD (ex. DBOPS_INVENTORY). */
export const SUGGESTED_INTEGRATION_TYPES = [
  'aap',
  'servicenow',
  'terraform',
  'azuredevops',
  'jira',
  'github_actions',
  'inventory',
  'inventory_db',
] as const;

/** Authentication flow types (Story 4.9 AC2). */
export type AuthFlow = 'token' | 'basic' | 'basic_then_token' | 'pat';

/** Labels for auth flows (french). */
export const AUTH_FLOW_LABELS: Record<AuthFlow, string> = {
  token: 'Token (Bearer)',
  basic: 'Basic (Username/Password)',
  basic_then_token: 'Basic puis Token',
  pat: 'PAT (Personal Access Token)',
};

/** Story 13.1: config for inventory_db (schema + table). */
export interface IntegrationConfigInventoryDb {
  schema?: string | null;
  table?: string | null;
}

export interface IntegrationCreate {
  type: string; // Story 4.9 AC1: free-form platform name (1-100 chars)
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
  auth_flow?: AuthFlow | null; // Story 4.9 AC2: authentication flow
  config?: IntegrationConfigInventoryDb | Record<string, unknown> | null; // Story 13.1: inventory_db schema/table
}

export interface IntegrationUpdate {
  type?: string; // Story 4.9 AC1: free-form platform name
  name?: string;
  base_url?: string;
  credential_ref?: string | null;
  icon?: string | null;
  auth_flow?: AuthFlow | null; // Story 4.9 AC2: authentication flow
  config?: IntegrationConfigInventoryDb | Record<string, unknown> | null; // Story 13.1: inventory_db schema/table
}

export interface IntegrationResponse {
  id: number;
  type: string; // Story 4.9 AC1: free-form platform name
  name: string;
  base_url: string;
  credential_ref: string | null;
  icon: string | null;
  auth_flow: AuthFlow | null; // Story 4.9 AC2: authentication flow
  config?: IntegrationConfigInventoryDb | Record<string, unknown> | null; // Story 13.1: inventory_db schema/table
  created_at: string;
  updated_at: string;
}

/** Alias for list display (same as full response). */
export type IntegrationListItem = IntegrationResponse;
