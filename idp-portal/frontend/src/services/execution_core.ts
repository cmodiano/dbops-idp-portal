/**
 * Execution core API — submit, get, list, approve, cancel, remediation.
 * Story 4.1; Story 7.4; Story 9.1, 9.2; Story 17.14.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import type {
  ExecutionCreateRequest,
  ExecutionCreateResponse,
  ExecutionResponse,
  ExecutionStepResponse,
  StepLogsResponse,
  ExecutionScope,
  ExecutionFilters,
  RemediationSuggestion,
  RemediationContext,
} from '../types/api';

/** Response shape for GET /executions (Story 4.8 AC4: pagination). */
export interface ListExecutionsResponse {
  data: ExecutionResponse[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

/** Response from GET /executions/pending-approvals (Story 7.4, AC2, AC6). */
export interface PendingApprovalsResponse {
  data: ExecutionResponse[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

/** Response from GET /executions/pending-approvals?count_only=true (Story 7.4, AC6). */
export interface PendingApprovalsCountResponse {
  count: number;
}

/** Response from POST /executions/{id}/approve (Story 7.4, AC3). */
export interface ApproveExecutionResponse {
  execution_id: number;
  status: string;
  approved_by: number;
  correlation_id: string;
}

/** Response from POST /executions/{id}/reject (Story 7.4, AC4). */
export interface RejectExecutionResponse {
  execution_id: number;
  status: string;
  rejected_by: number;
  rejection_reason: string | null;
}

/**
 * Build query string from filters (Story 9.10).
 */
export function buildFilterParams(filters?: ExecutionFilters): string {
  if (!filters) return '';
  const params = new URLSearchParams();
  if (filters.start_date) params.set('start_date', filters.start_date);
  if (filters.end_date) params.set('end_date', filters.end_date);
  if (filters.action_id) params.set('action_id', String(filters.action_id));
  if (filters.engine) params.set('engine', filters.engine);
  if (filters.tags && filters.tags.length > 0) params.set('tags', filters.tags.join(','));
  if (filters.status) params.set('status', filters.status);
  if (filters.environment) params.set('environment', filters.environment);
  return params.toString();
}

export async function submitExecution(
  request: ExecutionCreateRequest
): Promise<ExecutionCreateResponse> {
  return apiFetch<ExecutionCreateResponse>('/executions', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getExecution(executionId: number): Promise<ExecutionResponse> {
  return apiFetch<ExecutionResponse>(`/executions/${executionId}`);
}

export async function getExecutionSteps(
  executionId: number,
): Promise<ExecutionStepResponse[]> {
  return apiFetch<ExecutionStepResponse[]>(`/executions/${executionId}/steps`);
}

export async function getStepLogs(
  executionId: number,
  stepId: number,
): Promise<StepLogsResponse> {
  return apiFetch<StepLogsResponse>(`/executions/${executionId}/steps/${stepId}/logs`);
}

export async function listExecutions(
  limit = 50,
  offset = 0,
  scope: ExecutionScope = 'mine',
  filters?: ExecutionFilters
): Promise<ListExecutionsResponse> {
  const baseParams = `limit=${limit}&offset=${offset}&scope=${scope}`;
  const filterParams = buildFilterParams(filters);
  const queryString = filterParams ? `${baseParams}&${filterParams}` : baseParams;
  return apiFetchRaw<ListExecutionsResponse>(`/executions?${queryString}`);
}

export async function listPendingApprovals(
  limit = 50,
  offset = 0
): Promise<PendingApprovalsResponse> {
  return apiFetchRaw<PendingApprovalsResponse>(
    `/executions/pending-approvals?limit=${limit}&offset=${offset}`
  );
}

export async function getPendingApprovalsCount(): Promise<number> {
  const response = await apiFetchRaw<PendingApprovalsCountResponse>(
    '/executions/pending-approvals?count_only=true'
  );
  return response.count;
}

export async function approveExecution(
  executionId: number,
  comment?: string
): Promise<ApproveExecutionResponse> {
  const body = JSON.stringify(comment ? { comment } : {});
  return apiFetch<ApproveExecutionResponse>(`/executions/${executionId}/approve`, {
    method: 'POST',
    body,
  });
}

export async function rejectExecution(
  executionId: number,
  comment?: string
): Promise<RejectExecutionResponse> {
  const body = JSON.stringify(comment ? { comment } : {});
  return apiFetch<RejectExecutionResponse>(`/executions/${executionId}/reject`, {
    method: 'POST',
    body,
  });
}

export async function cancelExecution(
  executionId: number
): Promise<ExecutionResponse> {
  return apiFetch<ExecutionResponse>(`/executions/${executionId}/cancel`, {
    method: 'PATCH',
  });
}

export async function fetchRemediationSuggestions(
  executionId: number
): Promise<RemediationSuggestion[]> {
  return apiFetch<RemediationSuggestion[]>(`/executions/${executionId}/remediation`);
}

export async function fetchRemediationContext(
  executionId: number
): Promise<RemediationContext> {
  return apiFetch<RemediationContext>(`/executions/${executionId}/remediation-context`);
}
