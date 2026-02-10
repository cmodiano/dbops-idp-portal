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
