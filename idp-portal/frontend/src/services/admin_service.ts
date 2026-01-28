/**
 * Admin service for catalog actions (Story 2.1, AC #5).
 */

import { apiFetch } from './api_client';
import type {
  ActionCreate,
  ActionResponse,
  ActionDetail,
  ActionListItem,
  ActionStatus,
  ExecutionStepsUpdate,
  RbacPoliciesUpdate,
  StatusTransition,
  AdminActionsFilters,
  ActionListResponse,
} from '../types/api';

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
 * List all actions in the catalog for admin dashboard.
 * Returns ActionListItem with execution_count and pagination.
 * Requires DBOPS profile.
 * Story 2.4, AC #2.
 */
export async function getAdminActions(filters?: AdminActionsFilters): Promise<ActionListResponse> {
  const params = new URLSearchParams();
  if (filters?.status) params.append('status', filters.status);
  if (filters?.category) params.append('category', filters.category);
  if (filters?.engine) params.append('engine', filters.engine);
  if (filters?.page) params.append('page', filters.page.toString());
  if (filters?.page_size) params.append('page_size', filters.page_size.toString());
  
  const queryString = params.toString();
  return apiFetch<ActionListResponse>(`/admin/actions${queryString ? `?${queryString}` : ''}`);
}

/**
 * @deprecated Use getAdminActions() instead
 */
export async function listActions(status?: string): Promise<ActionListItem[]> {
  const filters: AdminActionsFilters = status ? { status: status as ActionStatus } : undefined;
  const response = await getAdminActions(filters);
  return response.data;
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

/**
 * Update action status via a valid transition.
 * Requires DBOPS profile.
 * Story 2.4, AC #1, #4, #5.
 *
 * Valid transitions:
 * - draft -> published (publish)
 * - published -> disabled (disable)
 * - disabled -> published (enable)
 */
export async function updateActionStatus(
  actionId: number,
  transition: StatusTransition
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ transition }),
  });
}
