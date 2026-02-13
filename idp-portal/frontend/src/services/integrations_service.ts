/**
 * Integrations service (Story 2.28). CRUD for remote platform integrations.
 * Uses apiFetch, routes /admin/integrations and /admin/integrations/{id}. Requires DBOPS profile.
 */

import { apiFetch } from './api_client';
import type {
  IntegrationCreate,
  IntegrationUpdate,
  IntegrationResponse,
  IntegrationTypeCatalogue,
  IntegrationValidationResponse,
  IntegrationValidateAllResponse,
} from '../types/api';

/** Story 24.2 AC1: Fetch integration type catalogue from backend. */
export async function getIntegrationTypes(): Promise<IntegrationTypeCatalogue[]> {
  const res = await apiFetch<IntegrationTypeCatalogue[]>('/integrations/types/');
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

export async function deleteIntegration(id: number): Promise<void> {
  await apiFetch<void>(`/admin/integrations/${id}/`, { method: 'DELETE' });
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
