/**
 * Story 28.4: Business rule policy catalogue API service.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import type {
  BusinessRulePolicyDetail,
  BusinessRulePolicyListResponse,
  BusinessRulePolicyPayload,
  BusinessRulePolicyFilters,
} from '../types/api';

/**
 * List business rule policies with optional filters.
 * GET /api/v1/admin/business-rule-policies/
 */
export async function getBusinessRulePolicies(
  filters?: BusinessRulePolicyFilters,
): Promise<BusinessRulePolicyListResponse> {
  const params = new URLSearchParams();
  if (filters?.step_type) params.append('step_type', filters.step_type);
  if (filters?.is_active !== undefined) params.append('is_active', String(filters.is_active));
  if (filters?.page) params.append('page', filters.page.toString());
  if (filters?.page_size) params.append('page_size', filters.page_size.toString());
  const queryString = params.toString();
  return apiFetchRaw<BusinessRulePolicyListResponse>(
    `/admin/business-rule-policies/${queryString ? `?${queryString}` : ''}`,
  );
}

/**
 * Get a single business rule policy by ID.
 * GET /api/v1/admin/business-rule-policies/{id}/
 */
export async function getBusinessRulePolicy(id: number): Promise<BusinessRulePolicyDetail> {
  return apiFetch<BusinessRulePolicyDetail>(`/admin/business-rule-policies/${id}/`);
}

/**
 * Create a new business rule policy.
 * POST /api/v1/admin/business-rule-policies/
 */
export async function createBusinessRulePolicy(
  payload: BusinessRulePolicyPayload,
): Promise<BusinessRulePolicyDetail> {
  return apiFetch<BusinessRulePolicyDetail>('/admin/business-rule-policies/', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/**
 * Update a business rule policy.
 * PATCH /api/v1/admin/business-rule-policies/{id}/
 */
export async function updateBusinessRulePolicy(
  id: number,
  payload: Partial<BusinessRulePolicyPayload>,
): Promise<BusinessRulePolicyDetail> {
  return apiFetch<BusinessRulePolicyDetail>(`/admin/business-rule-policies/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

/**
 * Delete a business rule policy.
 * DELETE /api/v1/admin/business-rule-policies/{id}/
 */
export async function deleteBusinessRulePolicy(id: number): Promise<void> {
  await apiFetch<void>(`/admin/business-rule-policies/${id}/`, { method: 'DELETE' });
}
