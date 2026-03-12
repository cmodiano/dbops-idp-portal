/**
 * Execution/inventory API — targets, inventory items, schema.
 * Story 4.1, 4.2; Story 23.6; Story 37.3; Story 62.3, 62.5; Story 71.1.
 */

import { apiFetch, apiFetchRaw } from './api_client';
import logger from './logger';
import type { InventoryItem, InventorySchema } from '../types/api';

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

const inventoryCache = new Map<string, { data: InventoryItem[]; timestamp: number }>();
const loadingPromises = new Map<string, Promise<InventoryItem[]>>();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

export async function fetchTargetsPaginated(search?: string): Promise<TargetsResponse> {
  const params = new URLSearchParams();
  params.set('page', '1');
  params.set('page_size', '5000');
  if (search) params.set('search', search);
  return apiFetchRaw<TargetsResponse>(`/inventory/targets?${params.toString()}`);
}

export async function fetchInventoryTargets(search?: string): Promise<InventoryTarget[]> {
  const response = await fetchTargetsPaginated(search);
  return response?.items ?? [];
}

export async function fetchInventoryItems(
  type: 'databases' | 'servers' | 'instances' | 'environments',
  environment?: string,
  options?: { server_names?: string[]; engine_type?: string }
): Promise<InventoryItem[]> {
  const queryParams = new URLSearchParams();
  if (environment) queryParams.set('environment', environment);
  if (options?.server_names && options.server_names.length > 0) {
    queryParams.set('server_names', options.server_names.join(','));
  }
  if (options?.engine_type) queryParams.set('engine_type', options.engine_type);
  const params = queryParams.toString() ? `?${queryParams.toString()}` : '';
  const serverNamesSuffix = options?.server_names && options.server_names.length > 0
    ? `_${options.server_names.join(',')}`
    : '';
  const engineTypeSuffix = options?.engine_type ? `_et_${options.engine_type}` : '';
  const cacheKey = `inventory_cache_${type}${environment ? `_${environment}` : ''}${serverNamesSuffix}${engineTypeSuffix}`;
  const apiKey = `${type}${params}`;

  if (type === 'environments' && !environment) {
    if (import.meta.env.DEV) {
      logger.debug('Shared cache - fetchInventoryItems(environments) using fetchEnvironments cache');
    }
    const { fetchEnvironments } = await import('./reference_service');
    const envStrings = await fetchEnvironments();
    const items: InventoryItem[] = envStrings.map((env) => ({
      id: env,
      name: env.charAt(0).toUpperCase() + env.slice(1),
      environment: null,
    }));
    inventoryCache.set(apiKey, { data: items, timestamp: Date.now() });
    return items;
  }

  const cached = inventoryCache.get(apiKey);
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const existingPromise = loadingPromises.get(apiKey);
  if (existingPromise) {
    return existingPromise;
  }

  const promise = (async () => {
    try {
      let data: { data?: InventoryItem[] };
      try {
        data = await apiFetchRaw<{ data?: InventoryItem[] }>(`/inventory/${type}${params}`);
      } catch (fetchError) {
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
      inventoryCache.set(apiKey, { data: items, timestamp: Date.now() });
      loadingPromises.delete(apiKey);

      if (items.length > 0) {
        sessionStorage.setItem(
          cacheKey,
          JSON.stringify({ items, timestamp: Date.now() })
        );
      }
      return items;
    } catch (err) {
      loadingPromises.delete(apiKey);
      if (err instanceof Error && (err as Error & { useCache?: boolean }).useCache) {
        throw err;
      }
      throw err;
    }
  })();

  loadingPromises.set(apiKey, promise);
  return promise;
}

export async function fetchInventorySchema(): Promise<InventorySchema> {
  return apiFetch<InventorySchema>('/inventory/schema');
}
