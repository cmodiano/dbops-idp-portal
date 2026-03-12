/**
 * Execution service (Story 4.1; Story 9.1, 9.2 remediation).
 *
 * Provides functions to submit executions, fetch inventory data, get remediation suggestions,
 * and fetch remediation context for failed executions.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import logger from './logger';
import type {
  ExecutionCreateRequest,
  ExecutionCreateResponse,
  ExecutionResponse,
  ExecutionStepResponse,
  StepLogsResponse,
  InventoryItem,
  InventorySchema,
  ExecutionScope,
  RemediationSuggestion,
  RemediationContext,
  DashboardStats,
  ExecutionFilters,
  DashboardTimeSeriesPoint,
} from '../types/api';

/** Target from inventory API (for pattern/manual resolution). */
export interface InventoryTarget {
  name: string;
  environment: string;
  target_type: string;
  metadata: Record<string, unknown> | null;
}

/** Response from GET /inventory/targets */
export interface TargetsResponse {
  items: InventoryTarget[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * Story 71.1, AC5: Fetch targets with pagination response for TargetSelector.
 * DIP: Removes direct apiFetchRaw import from TargetSelector.tsx.
 */
export async function fetchTargetsPaginated(search?: string): Promise<TargetsResponse> {
  const params = new URLSearchParams();
  params.set('page', '1');
  params.set('page_size', '5000');
  if (search) params.set('search', search);
  return apiFetchRaw<TargetsResponse>(`/inventory/targets?${params.toString()}`);
}

/**
 * Fetch targets from inventory API (RBAC filtered).
 * Used for pattern resolution and manual target validation.
 */
export async function fetchInventoryTargets(search?: string): Promise<InventoryTarget[]> {
  const response = await fetchTargetsPaginated(search);
  return response?.items ?? [];
}
/**
 * Submit a new execution (Story 4.1, Task 1.1; Story 9.2 remediation).
 *
 * @param request - Execution request (action_id, environment, parameters, parent_execution_id)
 * @returns ExecutionCreateResponse with execution_id, status, created_at
 * @throws Error if action not found (404), validation fails (400), or parent not visible (403)
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
    total: number;
    total_pages: number;
  };
}

/**
 * Build query string from filters (Story 9.10).
 */
function buildFilterParams(filters?: ExecutionFilters): string {
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

/**
 * List executions with scope filter (Story 4.1, 4.8, 8.9, 9.10).
 *
 * @param limit - Maximum number of executions to return (default 50)
 * @param offset - Offset for pagination (default 0)
 * @param scope - "mine" for user's executions (default), "all" for all executions (DBA/DBOPS only)
 * @param filters - Advanced filters (Story 9.10)
 * @returns ListExecutionsResponse with data and pagination (total for UI)
 */
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

// === Story 7.4: Approval Workflow Functions ===

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
  const body = JSON.stringify(comment ? { comment } : {});
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
  const body = JSON.stringify(comment ? { comment } : {});
  return apiFetch<RejectExecutionResponse>(`/executions/${executionId}/reject`, {
    method: 'POST',
    body,
  });
}

// === Story 9.4: Execution Statistics (AC3) ===

/**
 * Fetch execution statistics by scope and filters (Story 9.4, AC3; Story 9.10).
 *
 * Returns stats filtered by scope and advanced filters:
 * - scope=mine: Statistics for current user's executions only (default)
 * - scope=all: Global statistics (RBAC applied - DBA/DBOPS see all)
 *
 * @param scope - "mine" for user's stats (default), "all" for all stats
 * @param filters - Advanced filters (Story 9.10)
 * @returns DashboardStats with executions_jour, taux_succes_pct, executions_en_cours, executions_en_erreur
 * @throws Error if API call fails
 */
export async function fetchExecutionStats(
  scope: ExecutionScope = 'mine',
  filters?: ExecutionFilters
): Promise<DashboardStats> {
  const baseParams = `scope=${scope}`;
  const filterParams = buildFilterParams(filters);
  const queryString = filterParams ? `${baseParams}&${filterParams}` : baseParams;
  return apiFetch<DashboardStats>(`/executions/stats?${queryString}`);
}

// === Story 9.10: Time Series and Tags ===

/**
 * Fetch time series data for TrendLineChart (Story 9.10, AC5).
 *
 * Returns daily counts of success/failed executions.
 * Default period is last 7 days if no date filters provided.
 *
 * @param scope - "mine" for user's executions (default), "all" for all executions
 * @param filters - Advanced filters including date range
 * @returns Array of { date, success, failed } points
 */
export async function fetchExecutionTimeSeries(
  scope: ExecutionScope = 'mine',
  filters?: ExecutionFilters
): Promise<DashboardTimeSeriesPoint[]> {
  const baseParams = `scope=${scope}`;
  const filterParams = buildFilterParams(filters);
  const queryString = filterParams ? `${baseParams}&${filterParams}` : baseParams;
  return apiFetch<DashboardTimeSeriesPoint[]>(`/executions/timeseries?${queryString}`);
}

/**
 * Fetch available tags for filtering (Story 9.10, AC3).
 *
 * Returns distinct tags from actions that have been executed.
 *
 * @returns Array of tag names
 */
export async function fetchExecutionTags(): Promise<string[]> {
  return apiFetch<string[]>('/executions/tags');
}

// === Story 17.14: Cancel Execution ===

/**
 * Cancel an execution (Story 17.14, AC3).
 *
 * @param executionId - Execution ID to cancel
 * @returns ExecutionResponse with updated status (CANCELLED)
 * @throws Error if user cannot cancel (403), invalid status (400), or not found (404)
 */
export async function cancelExecution(
  executionId: number
): Promise<ExecutionResponse> {
  return apiFetch<ExecutionResponse>(`/executions/${executionId}/cancel`, {
    method: 'PATCH',
  });
}

// === Story 9.1: Remediation Suggestions (FR36) ===

/**
 * Fetch remediation suggestions for a failed execution (Story 9.1, AC5).
 *
 * Returns corrective action suggestions based on error_message matching
 * against remediation_rules configured on actions.
 *
 * @param executionId - Execution ID to get suggestions for
 * @returns Array of RemediationSuggestion (empty if no match or execution not FAILED)
 * @throws Error if execution not found (404) or user cannot view it (403)
 */
export async function fetchRemediationSuggestions(
  executionId: number
): Promise<RemediationSuggestion[]> {
  return apiFetch<RemediationSuggestion[]>(`/executions/${executionId}/remediation`);
}

// === Story 9.2: Remediation Context (AC2, AC3) ===

/**
 * Fetch remediation context for an execution (Story 9.2, AC2, AC3).
 *
 * Returns information about remediation attempts (child executions)
 * for a failed parent execution, including whether any succeeded.
 *
 * @param executionId - Parent execution ID to get remediation context for
 * @returns RemediationContext with has_remediation, successful_remediation, and remediation_actions
 * @throws Error if execution not found (404) or user cannot view it (403)
 */
export async function fetchRemediationContext(
  executionId: number
): Promise<RemediationContext> {
  return apiFetch<RemediationContext>(`/executions/${executionId}/remediation-context`);
}

/**
 * Fetch inventory items for dropdowns (Story 4.1, Task 2.1; Story 4.2, Task 4.1-4.2).
 *
 * @param type - Inventory type: 'databases', 'servers', 'environments'
 * @param environment - Optional environment filter
 * @returns Array of InventoryItem
 * @throws Error with code 'INVENTORY_UNAVAILABLE' if inventory unavailable (HTTP 503)
 */
// Shared cache for inventory items to prevent duplicate API calls
const inventoryCache = new Map<string, { data: InventoryItem[]; timestamp: number }>();
const loadingPromises = new Map<string, Promise<InventoryItem[]>>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export async function fetchInventoryItems(
  type: 'databases' | 'servers' | 'instances' | 'environments',
  environment?: string,
  /** Story 23.6 - Optional server names to filter instances/databases. Story 37.3 - engine_type filter. */
  options?: { server_names?: string[]; engine_type?: string }
): Promise<InventoryItem[]> {
  // Story 23.6 - Build query string with optional server_names filter
  const queryParams = new URLSearchParams();
  if (environment) queryParams.set('environment', environment);
  if (options?.server_names && options.server_names.length > 0) {
    queryParams.set('server_names', options.server_names.join(','));
  }
  // Story 37.3 - Pass engine_type for servers/instances/databases
  if (options?.engine_type) queryParams.set('engine_type', options.engine_type);
  const params = queryParams.toString() ? `?${queryParams.toString()}` : '';
  // MEDIUM-2 fix: Include server_names in cache key to prevent incorrect cache hits
  // Story 23.6 - Cache must differentiate by server_names filter
  const serverNamesSuffix = options?.server_names && options.server_names.length > 0
    ? `_${options.server_names.join(',')}`
    : '';
  // Story 37.3 - Include engine_type in cache key to prevent incorrect cache hits
  const engineTypeSuffix = options?.engine_type ? `_et_${options.engine_type}` : '';
  const cacheKey = `inventory_cache_${type}${environment ? `_${environment}` : ''}${serverNamesSuffix}${engineTypeSuffix}`;
  const apiKey = `${type}${params}`;

  // Special handling for environments: share cache with fetchEnvironments
  if (type === 'environments' && !environment) {
    if (import.meta.env.DEV) {
      logger.debug('Shared cache - fetchInventoryItems(environments) using fetchEnvironments cache');
    }
    const { fetchEnvironments } = await import('./reference_service');
    const envStrings = await fetchEnvironments();
    // Convert string[] to InventoryItem[] format
    const items: InventoryItem[] = envStrings.map((env) => ({
      id: env,
      name: env.charAt(0).toUpperCase() + env.slice(1),
      environment: null,
    }));
    // Cache in inventoryCache for consistency
    inventoryCache.set(apiKey, { data: items, timestamp: Date.now() });
    return items;
  }

  // Check memory cache first
  const cached = inventoryCache.get(apiKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  // Check if request is already in progress
  const existingPromise = loadingPromises.get(apiKey);
  if (existingPromise) {
    return existingPromise;
  }

  // Start new request
  const promise = (async () => {
    try {
      // SEC-4: Use authenticated client with JWT token and correlation ID
      let data: { data?: InventoryItem[] };
      try {
        data = await apiFetchRaw<{ data?: InventoryItem[] }>(`/inventory/${type}${params}`);
      } catch (fetchError) {
        // Handle 503 - Inventory unavailable, try sessionStorage cache
        if (fetchError instanceof Error && fetchError.message.includes('503')) {
          const cached = sessionStorage.getItem(cacheKey);
          if (cached) {
            let cachedData;
            try {
              cachedData = JSON.parse(cached);
            } catch (parseError) {
              logger.warn('Invalid inventory cache JSON', { error: parseError instanceof Error ? parseError.message : String(parseError) });
            }

            if (cachedData && typeof cachedData.timestamp === 'number' && Array.isArray(cachedData.items)) {
              const cacheTime = cachedData.timestamp;
              const now = Date.now();
              if (now - cacheTime < CACHE_TTL) {
                const error = new Error('Inventaire temporairement indisponible — dernières valeurs en cache');
                (error as Error & { code: string }).code = 'INVENTORY_UNAVAILABLE';
                (error as Error & { useCache: boolean }).useCache = true;
                (error as Error & { cachedItems: InventoryItem[] }).cachedItems = cachedData.items;
                throw error;
              }
            } else if (cachedData) {
              logger.warn('Invalid inventory cache structure (missing timestamp or items array)');
            }
          }
          const error = new Error('Inventaire temporairement indisponible — dernières valeurs en cache');
          (error as Error & { code: string }).code = 'INVENTORY_UNAVAILABLE';
          throw error;
        }
        throw fetchError;
      }

      const items = data.data || [];

      // Update memory cache
      inventoryCache.set(apiKey, { data: items, timestamp: Date.now() });
      loadingPromises.delete(apiKey);

      // Cache successful response in sessionStorage (Task 4.3, Story 22.17 MED-5)
      // Security: sessionStorage limits XSS exposure — cache cleared on tab close
      if (items.length > 0) {
        sessionStorage.setItem(
          cacheKey,
          JSON.stringify({
            items,
            timestamp: Date.now(),
          })
        );
      }

      return items;
    } catch (err) {
      loadingPromises.delete(apiKey);
      // Re-throw with cache info if available
      if (err instanceof Error && (err as Error & { useCache?: boolean }).useCache) {
        throw err;
      }
      throw err;
    }
  })();

  loadingPromises.set(apiKey, promise);
  return promise;
}

/**
 * Fetch available inventory column concepts per entity type from config.
 * Story 62.5 — Used by ParametersEditor to populate "Colonne valeur" options.
 * Endpoint created in Story 62.3: GET /api/v1/inventory/schema/
 */
export async function fetchInventorySchema(): Promise<InventorySchema> {
  return apiFetch<InventorySchema>('/inventory/schema');
}
