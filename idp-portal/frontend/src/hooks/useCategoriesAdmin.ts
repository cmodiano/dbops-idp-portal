/**
 * useCategoriesAdmin — Encapsulation DIP de getCategories/deleteCategory (categories_service).
 * Story 54.15 (SOLID-FE-4, AC1): Supprime les imports directs depuis categories_service dans CategoriesAdminTable.tsx.
 */

import { useState, useEffect, useCallback } from 'react';
import { getCategories, deleteCategory } from '../services/categories_service';
import { invalidateCategoriesCache } from './useCategories';
import type { RefCategory } from '../types/api';
import logger from '../services/logger';

export interface UseCategoriesAdminReturn {
  categories: RefCategory[];
  loading: boolean;
  error: string | null;
  handleDelete: (id: number) => Promise<void>;
  refresh: () => void;
}

export function useCategoriesAdmin(): UseCategoriesAdminReturn {
  const [categories, setCategories] = useState<RefCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getCategories(false)
      .then((data) => { if (!cancelled) setCategories(Array.isArray(data) ? data : []); })
      .catch((err) => {
        if (cancelled) return;
        const msg = err instanceof Error ? err.message : 'Erreur chargement catégories';
        logger.error('useCategoriesAdmin fetch failed', { error: msg });
        setError(msg);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [tick]);

  const refresh = useCallback(() => {
    setTick((t) => t + 1);
  }, []);

  const handleDelete = useCallback(async (id: number) => {
    await deleteCategory(id);
    invalidateCategoriesCache();
    setCategories((prev) => prev.filter((c) => c.id !== id));
  }, []);

  return { categories, loading, error, handleDelete, refresh };
}
