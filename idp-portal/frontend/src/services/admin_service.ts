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
  RemediationRule,
  WorkflowStepsUpdate,
  BusinessRulePoliciesData,
} from '../types/api';

/**
 * Create a new action in the catalog.
 * Requires DBOPS profile.
 */
export async function createAction(action: ActionCreate): Promise<ActionResponse> {
  return apiFetch<ActionResponse>('/admin/actions/', {
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
  // Story 18.1 (AC4/AC5): include disabled actions filter
  if (filters?.include_disabled) params.append('include_disabled', 'true');

  const queryString = params.toString();
  return apiFetchRaw<ActionListResponse>(`/admin/actions/${queryString ? `?${queryString}` : ''}`);
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
 * Check if an action name is available (no other action has this name).
 * For edit mode, pass the current action id to exclude it from the check.
 * Requires DBOPS profile.
 */
export async function checkActionNameAvailable(name: string, excludeId?: number): Promise<boolean> {
  const params = new URLSearchParams({ name: name.trim() });
  if (excludeId != null) params.set('exclude_id', String(excludeId));
  const res = await apiFetchRaw<{ available: boolean }>(`/admin/actions/name-available/?${params.toString()}`);
  return res?.available ?? true;
}

/**
 * Get action details by ID.
 * Requires DBOPS profile.
 */
export async function getAction(id: number): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${id}/`);
}

/**
 * Update action metadata (name, parameters_schema, impact_rules, etc.).
 * Requires DBOPS profile. Story 2.4, AC #3.
 * Story 2.23: category removed — use tags instead.
 */
export async function updateAction(actionId: number, action: ActionCreate): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/`, {
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
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/execution-steps/`, {
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
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/status/`, {
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
  return apiFetch<TagResponse[]>('/tags/');
}

/**
 * Update tags for an action. Create-on-the-fly when using tag_names.
 * Requires DBOPS profile. Story 2.6, AC #5.
 */
export async function updateActionTags(
  actionId: number,
  payload: { tag_ids?: number[]; tag_names?: string[] }
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/tags/`, {
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
  return apiFetch<AdminAnalytics>(`/admin/analytics/?days=${days}`);
}

/**
 * Update remediation rules for an action (Story 9.1, Task 6).
 * Requires DBOPS profile.
 *
 * @param actionId - Action ID
 * @param rules - Array of remediation rules (or null to clear)
 */
export async function updateRemediationRules(
  actionId: number,
  rules: RemediationRule[] | null
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/remediation-rules/`, {
    method: 'PUT',
    body: JSON.stringify({ remediation_rules: rules }),
  });
}

/**
 * Get actions eligible for workflow steps (Story 9.5, AC2).
 * Returns published actions only (no workflows).
 * Requires DBOPS profile.
 *
 * Uses apiFetchRaw to handle response format robustly (backend returns { data: [...] }).
 */
export async function getEligibleActionsForWorkflow(): Promise<ActionListItem[]> {
  const res = await apiFetchRaw<{ data?: ActionListItem[]; results?: ActionListItem[] }>(
    '/admin/actions/eligible-for-workflow/'
  );
  const list = res?.data ?? res?.results;
  return Array.isArray(list) ? list : [];
}

/**
 * Update workflow steps for a workflow (Story 9.5, AC3).
 * Uses the same execution-steps endpoint as actions (workflow steps stored in execution_steps).
 * Requires DBOPS profile.
 *
 * @param workflowId - Workflow action ID
 * @param data - Workflow steps to set
 */
export async function updateWorkflowSteps(
  workflowId: number,
  data: WorkflowStepsUpdate
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${workflowId}/execution-steps/`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

/**
 * Update business rule policies for an action (Story 28.1).
 * Requires DBOPS profile.
 *
 * @param actionId - Action ID
 * @param policies - Business rule policies data (or null to clear)
 */
export async function updateBusinessRulePolicies(
  actionId: number,
  policies: BusinessRulePoliciesData | null
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/business-rule-policies/`, {
    method: 'PUT',
    body: JSON.stringify({ business_rule_policies: policies }),
  });
}

/**
 * Patch action fields (partial update).
 * Story 28.4: Used for business_rule_policy_id FK assignment.
 * Requires DBOPS profile.
 */
export async function patchAction(
  actionId: number,
  data: Record<string, unknown>,
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

// ─── Story 18.1: Delete, Deactivate, Reactivate ───────────────────────────

/** Response from deactivate when workflows need confirmation. */
export interface DeactivateConfirmation {
  status: 'requires_confirmation';
  affected_workflows: { id: number; name: string; status: string }[];
}

/** Response from deactivate after confirmed. */
export interface DeactivateResult {
  data: ActionDetail;
  deactivated_workflows: { id: number; name: string }[];
}

/**
 * Hard-delete an action (only if execution_count=0).
 * Returns 204 on success, throws ApiError(409) if executions exist.
 * Story 18.1, AC1.
 */
export async function deleteAction(actionId: number): Promise<void> {
  await apiFetch<void>(`/admin/actions/${actionId}/`, { method: 'DELETE' });
}

/**
 * Deactivate (soft-delete) an action.
 * Without confirmed=true: returns affected workflows if any exist.
 * With confirmed=true: performs deactivation + cascade.
 * Story 18.1, AC2/AC3.
 */
export async function deactivateAction(
  actionId: number,
  reason?: string,
  confirmed = false,
): Promise<DeactivateConfirmation | DeactivateResult> {
  const url = `/admin/actions/${actionId}/deactivate/${confirmed ? '?confirmed=true' : ''}`;
  return apiFetchRaw<DeactivateConfirmation | DeactivateResult>(url, {
    method: 'PUT',
    body: JSON.stringify({ deletion_reason: reason }),
  });
}

/**
 * Reactivate a disabled action (sets status back to 'published').
 * Story 18.1, AC5.
 */
export async function reactivateAction(actionId: number): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/admin/actions/${actionId}/reactivate/`, {
    method: 'PUT',
  });
}
