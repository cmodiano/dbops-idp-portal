/**
 * Execution service (Story 4.1).
 *
 * Provides functions to submit executions and fetch inventory data.
 */

import { apiFetch } from './api_client';
import type {
  ExecutionCreateRequest,
  ExecutionCreateResponse,
  ExecutionResponse,
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
 * List user's executions (Story 4.1).
 *
 * @param limit - Maximum number of executions to return (default 50)
 * @param offset - Offset for pagination (default 0)
 * @returns Array of ExecutionResponse
 */
export async function listExecutions(
  limit = 50,
  offset = 0
): Promise<ExecutionResponse[]> {
  return apiFetch<ExecutionResponse[]>(`/executions?limit=${limit}&offset=${offset}`);
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
