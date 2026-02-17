/**
 * Hook to load environments from inventory API (Story 13.7).
 * Caches result to avoid multiple API calls.
 */

import { useState, useEffect } from 'react';
import { fetchEnvironments } from '../services/reference_service';

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
  // If cached, return immediately
  if (cachedEnvironments) {
    return Promise.resolve(cachedEnvironments);
  }
  
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
      listeners.forEach((listener) => listener(data, null));
      listeners.clear();
      return data;
    })
    .catch((err) => {
      const error = err instanceof Error ? err : new Error('Failed to load environments');
      cacheError = error;
      loadingPromise = null;
      const fallback = ['dev', 'staging', 'prod'];
      cachedEnvironments = fallback;
      listeners.forEach((listener) => listener(fallback, error));
      listeners.clear();
      // IMPORTANT: Do not rethrow. In test environments (and when inventory is temporarily down),
      // rethrowing leads to unhandled rejections and brittle UI tests.
      return fallback;
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
      setEnvironments(cachedEnvironments || ['dev', 'staging', 'prod']);
      setLoading(false);
      return;
    }

    let cancelled = false;

    // If already cached, use it immediately
    if (cachedEnvironments) {
      setEnvironments(cachedEnvironments);
      setLoading(false);
      setError(null);
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
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const error = err instanceof Error ? err : new Error('Failed to load environments');
          setError(error);
          // Fallback already set in cache by getOrFetchEnvironments
          setEnvironments(cachedEnvironments || ['dev', 'staging', 'prod']);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  // Convert to options format for Select components
  const environmentOptions = environments.map((env) => {
    // Map environment codes to display labels
    const labels: Record<string, string> = {
      'dev': 'Développement',
      'staging': 'Staging',
      'prod': 'Production',
    };
    return {
      value: env,
      label: labels[env.toLowerCase()] || (env.charAt(0).toUpperCase() + env.slice(1).toLowerCase()),
    };
  });

  return { environments, loading, error, environmentOptions };
}
