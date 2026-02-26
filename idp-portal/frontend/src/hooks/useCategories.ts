/**
 * Hook to load categories from reference API (Story 2.30).
 * Caches result to avoid multiple API calls.
 * Pattern: identical to useEngines (Story 13.7).
 */

import { useState, useEffect } from 'react';
import { getCategories } from '../services/categories_service';
import type { RefCategory } from '../types/api';

interface UseCategoriesResult {
  categories: RefCategory[];
  loading: boolean;
  error: Error | null;
  categoryOptions: { value: string; label: string }[];
}

// Shared cache across all hook instances
let cachedCategories: RefCategory[] | null = null;
let loadingPromise: Promise<RefCategory[]> | null = null;
let cacheError: Error | null = null;

// Atomic function to ensure only one request is made
function getOrFetchCategories(): Promise<RefCategory[]> {
  if (cachedCategories) {
    return Promise.resolve(cachedCategories);
  }
  if (loadingPromise) {
    return loadingPromise;
  }
  loadingPromise = getCategories(true)
    .then((data) => {
      cachedCategories = data;
      cacheError = null;
      loadingPromise = null;
      return data;
    })
    .catch((err) => {
      const error = err instanceof Error ? err : new Error('Failed to load categories');
      cacheError = error;
      loadingPromise = null;
      throw error;
    });
  return loadingPromise;
}

/**
 * Invalidate the shared categories cache (Story 48.7, AC1).
 * Forces next useCategories() mount to re-fetch from API.
 */
export function invalidateCategoriesCache(): void {
  cachedCategories = null;
  loadingPromise = null;
  cacheError = null;
}

/**
 * Hook to fetch and cache categories from REF_CATEGORIES table.
 * Returns categories as options array for Select components.
 * Uses shared cache to prevent duplicate API calls.
 */
export function useCategories(): UseCategoriesResult {
  const [categories, setCategories] = useState<RefCategory[]>(cachedCategories || []);
  const [loading, setLoading] = useState(!cachedCategories);
  const [error, setError] = useState<Error | null>(cacheError);

  useEffect(() => {
    let cancelled = false;

    if (cachedCategories) {
      setCategories(cachedCategories);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    getOrFetchCategories()
      .then((data) => {
        if (!cancelled) {
          setCategories(data);
          setLoading(false);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const error = err instanceof Error ? err : new Error('Failed to load categories');
          setError(error);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const categoryOptions = categories
    .filter((c) => c.is_active === 1)
    .sort((a, b) => a.display_order - b.display_order || a.code.localeCompare(b.code))
    .map((c) => ({
      value: c.code,
      label: c.label,
    }));

  return { categories, loading, error, categoryOptions };
}
