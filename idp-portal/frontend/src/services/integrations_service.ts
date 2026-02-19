/**
 * Integrations service (Story 2.28). CRUD for remote platform integrations.
 * Uses apiFetch, routes /admin/integrations and /admin/integrations/{id}. Requires DBOPS profile.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import type {
  IntegrationCreate,
  IntegrationUpdate,
  IntegrationResponse,
  IntegrationTypeCatalogue,
  IntegrationValidationResponse,
  IntegrationValidateAllResponse,
} from '../types/api';

/** Story 24.2 AC1: Fetch integration type catalogue from backend.
 * Story 29.1: Optional role filter ('platform' | 'service').
 */
export async function getIntegrationTypes(
  role?: 'platform' | 'service',
): Promise<IntegrationTypeCatalogue[]> {
  const url = role ? `/integrations/types/?role=${role}` : '/integrations/types/';
  const res = await apiFetch<IntegrationTypeCatalogue[]>(url);
  // MEDIUM-3 fix: Handle { data: null } case
  return Array.isArray(res) ? res : [];
}

export async function getIntegrations(): Promise<IntegrationResponse[]> {
  const res = await apiFetch<IntegrationResponse[]>('/admin/integrations/');
  return res ?? [];
}

export async function getIntegration(id: number): Promise<IntegrationResponse> {
  return apiFetch<IntegrationResponse>(`/admin/integrations/${id}/`);
}

export async function createIntegration(payload: IntegrationCreate): Promise<IntegrationResponse> {
  return apiFetch<IntegrationResponse>('/admin/integrations/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateIntegration(
  id: number,
  payload: IntegrationUpdate,
): Promise<IntegrationResponse> {
  return apiFetch<IntegrationResponse>(`/admin/integrations/${id}/`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/** Story 31.2: Returns disabled_actions_count (0 if no actions were disabled). */
export async function deleteIntegration(id: number): Promise<{ disabled_actions_count: number }> {
  const res = await apiFetchRaw<{ disabled_actions_count: number } | undefined>(
    `/admin/integrations/${id}/`,
    { method: 'DELETE' },
  );
  return res ?? { disabled_actions_count: 0 };
}

/** Story 24.3: Validate a single integration against the type catalogue. */
export async function validateIntegration(id: number): Promise<IntegrationValidationResponse> {
  return apiFetch<IntegrationValidationResponse>(`/admin/integrations/${id}/validate/`);
}

/** Story 24.3: Batch validate all integrations. */
export async function validateAllIntegrations(): Promise<IntegrationValidateAllResponse> {
  return apiFetch<IntegrationValidateAllResponse>('/admin/integrations/validate-all/', {
    method: 'POST',
  });
}
