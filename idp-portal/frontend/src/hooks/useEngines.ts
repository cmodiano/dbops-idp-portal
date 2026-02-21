/**
 * Hook to load engines from reference API (Story 13.7).
 * Caches result to avoid multiple API calls.
 */

import { useState, useEffect } from 'react';
import { fetchEngines, type RefEngine } from '../services/reference_service';

interface UseEnginesResult {
  engines: RefEngine[];
  loading: boolean;
  error: Error | null;
  engineOptions: { value: string; label: string }[];
}

// Shared cache across all hook instances
let cachedEngines: RefEngine[] | null = null;
let loadingPromise: Promise<RefEngine[]> | null = null;
let cacheError: Error | null = null;

// Atomic function to ensure only one request is made
function getOrFetchEngines(): Promise<RefEngine[]> {
  // If cached, return immediately
  if (cachedEngines) {
    return Promise.resolve(cachedEngines);
  }
  
  // If already loading, return existing promise
  if (loadingPromise) {
    return loadingPromise;
  }
  
  // Start new request atomically
  loadingPromise = fetchEngines()
    .then((data) => {
      cachedEngines = data;
      cacheError = null;
      loadingPromise = null;
      return data;
    })
    .catch((err) => {
      const error = err instanceof Error ? err : new Error('Failed to load engines');
      cacheError = error;
      loadingPromise = null;
      throw error;
    });
  
  return loadingPromise;
}

/**
 * Hook to fetch and cache engines from REF_ENGINES table.
 * Returns engines as options array for Select components.
 * Uses shared cache to prevent duplicate API calls.
 */
export function useEngines(): UseEnginesResult {
  const [engines, setEngines] = useState<RefEngine[]>(cachedEngines || []);
  const [loading, setLoading] = useState(!cachedEngines);
  const [error, setError] = useState<Error | null>(cacheError);

  useEffect(() => {
    let cancelled = false;

    // If already cached, use it immediately
    if (cachedEngines) {
      setEngines(cachedEngines);
      setLoading(false);
      setError(null);
      return;
    }

    // Use atomic function to get or fetch
    setLoading(true);
    setError(null);
    
    getOrFetchEngines()
      .then((data) => {
        if (!cancelled) {
          setEngines(data);
          setLoading(false);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const error = err instanceof Error ? err : new Error('Failed to load engines');
          setError(error);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // Convert to options format for Select components
  const engineOptions = engines
    .filter((e) => e.is_active === 1)
    .sort((a, b) => a.display_order - b.display_order || a.code.localeCompare(b.code))
    .map((e) => ({
      value: e.code,
      label: e.label,
    }));

  return { engines, loading, error, engineOptions };
}

/**
 * Invalidate the shared engines cache (Story 31.10, AC3).
 * Forces next useEngines() mount to re-fetch from API.
 */
export function invalidateEnginesCache(): void {
  cachedEngines = null;
  loadingPromise = null;
  cacheError = null;
}
