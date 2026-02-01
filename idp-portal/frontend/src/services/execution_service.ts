/**
 * Execution service (Story 4.1).
 *
 * Provides functions to submit executions and fetch inventory data.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import type {
  ExecutionCreateRequest,
  ExecutionCreateResponse,
  ExecutionResponse,
  ExecutionStepResponse,
  StepLogsResponse,
  InventoryItem,
} from '../types/api';

/**
 * Submit a new execution (Story 4.1, Task 1.1).
 *
 * @param request - Execution request (action_id, environment, parameters)
 * @returns ExecutionCreateResponse with execution_id, status, created_at
 * @throws Error if action not found (404) or validation fails (400)
 */
export async function submitExecution(
  request: ExecutionCreateRequest
): Promise<ExecutionCreateResponse> {
  return apiFetch<ExecutionCreateResponse>('/executions', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Get execution by ID (Story 4.1).
 *
 * @param executionId - Execution ID
 * @returns ExecutionResponse with full execution details
 * @throws Error if execution not found (404)
 */
export async function getExecution(executionId: number): Promise<ExecutionResponse> {
  return apiFetch<ExecutionResponse>(`/executions/${executionId}`);
}

/**
 * Get execution steps by ID (Story 4.6, Task 2.4).
 *
 * @param executionId - Execution ID
 * @returns Array of ExecutionStepResponse
 * @throws Error if execution not found (404)
 */
export async function getExecutionSteps(
  executionId: number,
): Promise<ExecutionStepResponse[]> {
  return apiFetch<ExecutionStepResponse[]>(`/executions/${executionId}/steps`);
}

/**
 * Get step logs (Story 4.7, AC6).
 *
 * @param executionId - Execution ID
 * @param stepId - Step ID
 * @returns StepLogsResponse with output, error_message, timestamps
 * @throws Error if execution or step not found (404)
 */
export async function getStepLogs(
  executionId: number,
  stepId: number,
): Promise<StepLogsResponse> {
  return apiFetch<StepLogsResponse>(`/executions/${executionId}/steps/${stepId}/logs`);
}

/** Response shape for GET /executions (Story 4.8 AC4: pagination). */
export interface ListExecutionsResponse {
  data: ExecutionResponse[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
  };
}

/**
 * List user's executions (Story 4.1, 4.8 AC4).
 *
 * @param limit - Maximum number of executions to return (default 50)
 * @param offset - Offset for pagination (default 0)
 * @returns ListExecutionsResponse with data and pagination (total_count for UI)
 */
export async function listExecutions(
  limit = 50,
  offset = 0
): Promise<ListExecutionsResponse> {
  return apiFetchRaw<ListExecutionsResponse>(
    `/executions?limit=${limit}&offset=${offset}`
  );
}

// === Story 7.4: Approval Workflow Functions ===

/** Response from GET /executions/pending-approvals (Story 7.4, AC2, AC6). */
export interface PendingApprovalsResponse {
  data: ExecutionResponse[];
  pagination: {
    page: number;
    page_size: number;
    total_count: number;
    total_pages: number;
  };
}

/** Response from GET /executions/pending-approvals?count_only=true (Story 7.4, AC6). */
export interface PendingApprovalsCountResponse {
  count: number;
}

/**
 * List pending approval executions (Story 7.4, AC2, AC6).
 *
 * @param limit - Maximum number of executions to return (default 50)
 * @param offset - Offset for pagination (default 0)
 * @returns PendingApprovalsResponse with data and pagination
 * @throws Error if user is not DBA/DBOPS (403)
 */
export async function listPendingApprovals(
  limit = 50,
  offset = 0
): Promise<PendingApprovalsResponse> {
  return apiFetchRaw<PendingApprovalsResponse>(
    `/executions/pending-approvals?limit=${limit}&offset=${offset}`
  );
}

/**
 * Get count of pending approval executions (Story 7.4, AC6 - for badge).
 *
 * @returns Object with count
 * @throws Error if user is not DBA/DBOPS (403)
 */
export async function getPendingApprovalsCount(): Promise<number> {
  const response = await apiFetchRaw<PendingApprovalsCountResponse>(
    '/executions/pending-approvals?count_only=true'
  );
  return response.count;
}

/** Response from POST /executions/{id}/approve (Story 7.4, AC3). */
export interface ApproveExecutionResponse {
  execution_id: number;
  status: string;
  approved_by: number;
  correlation_id: string;
}

/**
 * Approve an execution (Story 7.4, AC3, AC5).
 *
 * @param executionId - Execution ID to approve
 * @param comment - Optional approval comment
 * @returns ApproveExecutionResponse
 * @throws Error if user cannot approve (403), or execution not found/wrong status (404/400)
 */
export async function approveExecution(
  executionId: number,
  comment?: string
): Promise<ApproveExecutionResponse> {
  const body = comment ? JSON.stringify({ comment }) : undefined;
  return apiFetch<ApproveExecutionResponse>(`/executions/${executionId}/approve`, {
    method: 'POST',
    body,
  });
}

/** Response from POST /executions/{id}/reject (Story 7.4, AC4). */
export interface RejectExecutionResponse {
  execution_id: number;
  status: string;
  rejected_by: number;
  rejection_reason: string | null;
}

/**
 * Reject an execution (Story 7.4, AC4, AC5).
 *
 * @param executionId - Execution ID to reject
 * @param comment - Optional rejection reason
 * @returns RejectExecutionResponse
 * @throws Error if user cannot reject (403), or execution not found/wrong status (404/400)
 */
export async function rejectExecution(
  executionId: number,
  comment?: string
): Promise<RejectExecutionResponse> {
  const body = comment ? JSON.stringify({ comment }) : undefined;
  return apiFetch<RejectExecutionResponse>(`/executions/${executionId}/reject`, {
    method: 'POST',
    body,
  });
}

/**
 * Fetch inventory items for dropdowns (Story 4.1, Task 2.1; Story 4.2, Task 4.1-4.2).
 *
 * @param type - Inventory type: 'databases', 'servers', 'environments'
 * @param environment - Optional environment filter
 * @returns Array of InventoryItem
 * @throws Error with code 'INVENTORY_UNAVAILABLE' if inventory unavailable (HTTP 503)
 */
export async function fetchInventoryItems(
  type: 'databases' | 'servers' | 'environments',
  environment?: string
): Promise<InventoryItem[]> {
  const params = environment ? `?environment=${encodeURIComponent(environment)}` : '';
  const cacheKey = `inventory_cache_${type}${environment ? `_${environment}` : ''}`;

  try {
    const response = await fetch(`/api/v1/inventory/${type}${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 503) {
        // Inventory unavailable - try to use localStorage cache if available (Task 4.2, 4.3)
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          try {
            const cachedData = JSON.parse(cached);
            const cacheTime = cachedData.timestamp;
            const now = Date.now();
            // Use cache if less than 5 minutes old (Task 4.3)
            if (now - cacheTime < 5 * 60 * 1000) {
              const error = new Error('Inventaire temporairement indisponible — dernières valeurs en cache');
              (error as Error & { code: string }).code = 'INVENTORY_UNAVAILABLE';
              (error as Error & { useCache: boolean }).useCache = true;
              (error as Error & { cachedItems: InventoryItem[] }).cachedItems = cachedData.items;
              throw error;
            }
          } catch (parseError) {
            // Invalid cache JSON or missing timestamp - log and continue to throw original error
            console.warn('Invalid inventory cache format', parseError);
          }
        }
        const error = new Error('Inventaire temporairement indisponible — dernières valeurs en cache');
        (error as Error & { code: string }).code = 'INVENTORY_UNAVAILABLE';
        throw error;
      }
      throw new Error(`Failed to fetch inventory: ${response.statusText}`);
    }

    const data = await response.json();
    const items = data.data || [];

    // Cache successful response in localStorage (Task 4.3)
    if (items.length > 0) {
      localStorage.setItem(
        cacheKey,
        JSON.stringify({
          items,
          timestamp: Date.now(),
        })
      );
    }

    return items;
  } catch (err) {
    // Re-throw with cache info if available
    if (err instanceof Error && (err as Error & { useCache?: boolean }).useCache) {
      throw err;
    }
    throw err;
  }
}
