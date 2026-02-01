/**
 * Admin service for catalog actions (Story 2.1, AC #5).
 */

import { apiFetch, apiFetchRaw } from './api_client';
import type {
  ActionCreate,
  ActionResponse,
  ActionDetail,
  ActionListItem,
  ActionStatus,
  ExecutionStepsUpdate,
  StatusTransition,
  AdminActionsFilters,
  ActionListResponse,
  AdminAnalytics,
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
  if (filters?.engine) params.append('engine', filters.engine);
  if (filters?.page) params.append('page', filters.page.toString());
  if (filters?.page_size) params.append('page_size', filters.page_size.toString());

  const queryString = params.toString();
  // Use apiFetchRaw so we get { data, pagination }; apiFetch would return only body.data (the array).
  return apiFetchRaw<ActionListResponse>(`/admin/actions${queryString ? `?${queryString}` : ''}`);
}

/**
 * @deprecated Use getAdminActions() instead
 */
export async function listActions(status?: string): Promise<ActionListItem[]> {
  const filters: AdminActionsFilters | undefined = status ? { status: status as ActionStatus } : undefined;
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
 * Update action metadata (name, parameters_schema, impact_rules, etc.).
 * Requires DBOPS profile. Story 2.4, AC #3.
 * Story 2.23: category removed — use tags instead.
 */
export async function updateAction(actionId: number, action: ActionCreate): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}`, {
    method: 'PUT',
    body: JSON.stringify(action),
  });
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

/** Tag from GET /api/v1/tags (Story 2.6, AC #5). */
export interface TagResponse {
  id: number;
  name: string;
  created_at: string;
}

/**
 * Fetch all tags for autocomplete (admin Tags section, catalogue).
 * Story 2.6, AC #5.
 */
export async function getTags(): Promise<TagResponse[]> {
  return apiFetch<TagResponse[]>('/tags');
}

/**
 * Update tags for an action. Create-on-the-fly when using tag_names.
 * Requires DBOPS profile. Story 2.6, AC #5.
 */
export async function updateActionTags(
  actionId: number,
  payload: { tag_ids?: number[]; tag_names?: string[] }
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/tags`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

/**
 * Fetch admin analytics dashboard data (Story 8.2, AC4).
 * Requires DBOPS profile.
 *
 * @param days - Period in days (30, 90, 365). Default 90.
 */
export async function fetchAdminAnalytics(days: number = 90): Promise<AdminAnalytics> {
  return apiFetch<AdminAnalytics>(`/admin/analytics?days=${days}`);
}
