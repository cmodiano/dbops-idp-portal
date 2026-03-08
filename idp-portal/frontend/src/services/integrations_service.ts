/**
 * Integrations service (Story 2.28). CRUD for remote platform integrations.
 * Uses apiFetch, routes /admin/integrations and /admin/integrations/{id}. Requires DBOPS profile.
 */

import { apiFetch, apiFetchBlob, apiFetchRaw } from './api_client';
import type {
  IntegrationCreate,
  IntegrationUpdate,
  IntegrationResponse,
  IntegrationTypeCatalogue,
  IntegrationValidationResponse,
  IntegrationValidateAllResponse,
  AAPTemplate,
  AAPTemplatesResponse,
  TestConnectionResponse,
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

/** Story 31.6: Fetch integrations filtered by type (e.g. 'servicenow', 'aap'). */
export async function getIntegrationsByType(type: string): Promise<IntegrationResponse[]> {
  const res = await apiFetch<IntegrationResponse[]>(`/admin/integrations/?type=${encodeURIComponent(type)}`);
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

/** Story 51.4: Déclenche un health check synchrone sur une intégration.
 * POST /admin/integrations/{id}/test-connection/
 */
export async function testConnection(id: number): Promise<TestConnectionResponse> {
  return apiFetch<TestConnectionResponse>(`/admin/integrations/${id}/test-connection/`, {
    method: 'POST',
  });
}

/** Story 31.5: Fetch AAP templates (job or workflow) for a given integration.
 * H1 fix: throws on API error so useAAPTemplates hook can set error state (Alert visible).
 */
export async function getAAPTemplates(
  integrationId: number,
  resourceType: 'job_template' | 'workflow_job',
  search?: string,
): Promise<{ templates: AAPTemplate[]; fallback: boolean }> {
  const params = new URLSearchParams({ resource_type: resourceType });
  if (search) params.set('search', search);
  const res = await apiFetch<AAPTemplatesResponse>(
    `/admin/integrations/${integrationId}/aap-templates/?${params.toString()}`,
  );
  return { templates: res?.data ?? [], fallback: res?.fallback ?? false };
}

/** Story 64.13: Export a single integration as YAML file. Triggers browser download. */
export async function exportIntegrationYaml(id: number, name: string): Promise<void> {
  const blob = await apiFetchBlob(`/admin/integrations/${id}/export/yaml/`);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `integrations-${name}.yaml`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
