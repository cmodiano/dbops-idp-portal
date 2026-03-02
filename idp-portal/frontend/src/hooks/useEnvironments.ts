/**
 * Hook to load environments from inventory API (Story 13.7).
 * Caches result to avoid multiple API calls.
 */

import { useState, useEffect } from 'react';
import { fetchEnvironments } from '../services/reference_service';
import { getEnvironmentLabel } from '../utils/environmentHelpers';

interface UseEnvironmentsResult {
  environments: string[];
  loading: boolean;
  error: Error | null;
  environmentOptions: { value: string; label: string }[];
}

// Shared cache across all hook instances
let cachedEnvironments: string[] | null = null;
let loadingPromise: Promise<string[]> | null = null;
let cacheError: Error | null = null;
const listeners: Set<(data: string[], error: Error | null) => void> = new Set();

/**
 * Invalidate the environments cache.
 * Forces next hook call to refetch from API.
 * Useful for testing or when inventory data changes.
 */
export function invalidateEnvironmentsCache(): void {
  cachedEnvironments = null;
  loadingPromise = null;
  cacheError = null;
  listeners.clear();
}

// Atomic function to ensure only one request is made
function getOrFetchEnvironments(): Promise<string[]> {
  // If cached, return immediately (defensive: hook pre-checks before calling this function)
  /* v8 ignore start */
  if (cachedEnvironments !== null) {
    return Promise.resolve(cachedEnvironments);
  }
  /* v8 ignore stop */
  
  // If already loading, return existing promise
  if (loadingPromise) {
    return loadingPromise;
  }
  
  // Start new request atomically
  loadingPromise = fetchEnvironments()
    .then((data) => {
      cachedEnvironments = data;
      cacheError = null;
      loadingPromise = null;
      /* v8 ignore start */
      listeners.forEach((listener) => listener(data, null));
      /* v8 ignore stop */
      listeners.clear();
      return data;
    })
    .catch((err) => {
      const error = err instanceof Error ? err : new Error('Failed to load environments');
      cacheError = error;
      loadingPromise = null;
      cachedEnvironments = [];  // liste vide — pas de fallback fictif
      /* v8 ignore start */
      listeners.forEach((listener) => listener([], error));
      /* v8 ignore stop */
      listeners.clear();
      // IMPORTANT: Do not rethrow. In test environments (and when inventory is temporarily down),
      // rethrowing leads to unhandled rejections and brittle UI tests.
      return [];
    });
  
  return loadingPromise;
}

export interface UseEnvironmentsOptions {
  /** When false, skip the API call (avoids 401 when auth not ready). Default true. */
  enabled?: boolean;
}

/**
 * Hook to fetch and cache environments from inventory.
 * Returns environments as options array for Select components.
 * Uses shared cache to prevent duplicate API calls.
 * Pass { enabled: !!user } to avoid 401 when auth is not ready.
 */
export function useEnvironments(options?: UseEnvironmentsOptions): UseEnvironmentsResult {
  const enabled = options?.enabled !== false;
  const [environments, setEnvironments] = useState<string[]>(cachedEnvironments || []);
  const [loading, setLoading] = useState(!cachedEnvironments && enabled);
  const [error, setError] = useState<Error | null>(cacheError);

  useEffect(() => {
    if (!enabled) {
      setEnvironments(cachedEnvironments || []);
      setLoading(false);
      return;
    }

    let cancelled = false;

    // If already cached, use it immediately (preserve cacheError if fetch previously failed)
    if (cachedEnvironments !== null) {
      setEnvironments(cachedEnvironments);
      setLoading(false);
      setError(cacheError);
      return;
    }

    // Use atomic function to get or fetch
    setLoading(true);
    setError(null);
    
    getOrFetchEnvironments()
      .then((data) => {
        if (!cancelled) {
          setEnvironments(data);
          setLoading(false);
          // Preserve error from cache if fetch failed (getOrFetchEnvironments resolves [] on error)
          setError(cacheError);
        }
      })
      /* v8 ignore start */
      .catch((err) => {
        if (!cancelled) {
          const error = err instanceof Error ? err : new Error('Failed to load environments');
          setError(error);
          // Fallback already set in cache by getOrFetchEnvironments
          setEnvironments(cachedEnvironments || []);
          setLoading(false);
        }
      });
      /* v8 ignore stop */

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  // Convert to options format for Select components
  const environmentOptions = environments.map((env) => ({
    value: env,
    label: getEnvironmentLabel(env),
  }));

  return { environments, loading, error, environmentOptions };
}
