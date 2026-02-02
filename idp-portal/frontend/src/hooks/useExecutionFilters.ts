/**
 * useExecutionFilters - Hook for managing execution filters with URL sync (Story 9.10, AC7, AC8).
 *
 * Provides:
 * - filters: Current filter state
 * - applyFilters: Update filters and sync to URL
 * - resetFilters: Clear all filters
 * - activeFilterCount: Number of active (non-default) filters
 *
 * AC7: Filters persist in URL query params for sharing and refresh
 * AC8: Badge shows active filter count
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router';
import type { ExecutionFilters, ExecutionStatusType, ExecutionEnvironment } from '../types/api';

/** Default filters (no filtering applied). */
const DEFAULT_FILTERS: ExecutionFilters = {
  start_date: null,
  end_date: null,
  action_id: null,
  engine: null,
  tags: null,
  status: null,
  environment: null,
};

/** Parse URL query params into ExecutionFilters. */
function parseFiltersFromURL(search: string): ExecutionFilters {
  const params = new URLSearchParams(search);

  return {
    start_date: params.get('start_date') || null,
    end_date: params.get('end_date') || null,
    action_id: params.get('action_id') ? parseInt(params.get('action_id')!, 10) : null,
    engine: params.get('engine') || null,
    tags: params.get('tags') ? params.get('tags')!.split(',').filter(Boolean) : null,
    status: (params.get('status') as ExecutionStatusType) || null,
    environment: (params.get('environment') as ExecutionEnvironment) || null,
  };
}

/** Build URL query string from filters. */
function buildURLFromFilters(filters: ExecutionFilters): string {
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

/** Count number of active (non-null/non-empty) filters. */
function countActiveFilters(filters: ExecutionFilters): number {
  let count = 0;
  if (filters.start_date || filters.end_date) count++;
  if (filters.action_id) count++;
  if (filters.engine) count++;
  if (filters.tags && filters.tags.length > 0) count++;
  if (filters.status) count++;
  if (filters.environment) count++;
  return count;
}

export interface UseExecutionFiltersResult {
  /** Current filter values. */
  filters: ExecutionFilters;
  /** Apply new filters (merges with existing, updates URL). */
  applyFilters: (newFilters: ExecutionFilters) => void;
  /** Reset all filters to defaults. */
  resetFilters: () => void;
  /** Number of active filters (for badge). */
  activeFilterCount: number;
  /** Whether any filter is active. */
  hasActiveFilters: boolean;
}

export function useExecutionFilters(): UseExecutionFiltersResult {
  const navigate = useNavigate();
  const location = useLocation();

  // Initialize filters from URL on mount
  const [filters, setFilters] = useState<ExecutionFilters>(() =>
    parseFiltersFromURL(location.search)
  );

  // Sync filters from URL when location changes (e.g., browser back/forward)
  useEffect(() => {
    const urlFilters = parseFiltersFromURL(location.search);
    setFilters(urlFilters);
  }, [location.search]);

  // Calculate active filter count
  const activeFilterCount = useMemo(() => countActiveFilters(filters), [filters]);
  const hasActiveFilters = activeFilterCount > 0;

  // Apply new filters and update URL
  const applyFilters = useCallback(
    (newFilters: ExecutionFilters) => {
      setFilters(newFilters);
      const queryString = buildURLFromFilters(newFilters);
      navigate({ search: queryString }, { replace: true });
    },
    [navigate]
  );

  // Reset all filters
  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    navigate({ search: '' }, { replace: true });
  }, [navigate]);

  return {
    filters,
    applyFilters,
    resetFilters,
    activeFilterCount,
    hasActiveFilters,
  };
}

export default useExecutionFilters;
