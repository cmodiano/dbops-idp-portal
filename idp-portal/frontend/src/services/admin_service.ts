/**
 * Admin service for catalog actions (Story 2.1, AC #5).
 */

import { apiFetch } from './api_client';
import type { ActionCreate, ActionResponse, ActionDetail, ExecutionStepsUpdate, RbacPoliciesUpdate } from '../types/api';

/**
 * Create a new action in the catalog.
 * Requires DBOPS profile.
 */
export async function createAction(action: ActionCreate): Promise<ActionResponse> {
  return apiFetch<ActionResponse>('/admin/actions', {
    method: 'POST',
    body: JSON.stringify(action),
  });
}

/**
 * List all actions in the catalog.
 * Requires DBOPS profile.
 */
export async function listActions(status?: string): Promise<ActionResponse[]> {
  const params = status ? `?status_filter=${status}` : '';
  return apiFetch<ActionResponse[]>(`/admin/actions${params}`);
}

/**
 * Get action details by ID.
 * Requires DBOPS profile.
 */
export async function getAction(id: number): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${id}`);
}

/**
 * Update execution steps and change type config for an action.
 * Requires DBOPS profile. Action must be in draft status.
 * Story 2.2, AC #5.
 */
export async function updateActionSteps(
  actionId: number,
  data: ExecutionStepsUpdate
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/steps`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Update RBAC policies for an action.
 * Requires DBOPS profile. Action must be in draft status.
 * Story 2.3, AC #4.
 */
export async function updateActionRbac(
  actionId: number,
  data: RbacPoliciesUpdate
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/rbac`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
