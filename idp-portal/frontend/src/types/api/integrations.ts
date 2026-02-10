// === Integration Types (Story 2.28, 4.9, 24.2) ===

/** Story 24.2 AC1: Integration type catalogue from backend API. */
export interface IntegrationAction {
  id: number;
  action_code: string;
  action_label: string;
  description: string;
  required_params: Record<string, unknown>;
  optional_params: Record<string, unknown>;
  response_format: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/** Story 24.2 AC1: Integration type catalogue entry from GET /api/v1/integrations/types. */
export interface IntegrationTypeCatalogue {
  code: string;
  name: string;
  description: string;
  version: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  actions: IntegrationAction[];
}

/**
 * Story 24.2 AC5: Fallback types when API is unavailable.
 *
 * Used by useIntegrationTypes hook when GET /api/v1/integrations/types fails.
 * Provides minimal type list (AAP, ServiceNow) to allow degraded mode operation.
 *
 * LOW-5 fix: Document usage
 */
export const FALLBACK_INTEGRATION_TYPES: IntegrationTypeCatalogue[] = [
  {
    code: 'aap',
    name: 'Ansible Automation Platform',
    description: 'Exécution de jobs et workflows Ansible (fallback)',
    version: '1.0',
    is_active: true,
    actions: [],
    created_at: '',
    updated_at: '',
  },
  {
    code: 'servicenow',
    name: 'ServiceNow ITSM',
    description: 'Gestion des change requests (fallback)',
    version: '1.0',
    is_active: true,
    actions: [],
    created_at: '',
    updated_at: '',
  },
];

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
