/**
 * useUrlFilters - Hook to sync dashboard filters with URL query parameters and localStorage.
 * Story 8.4, AC6 (URL persistence), AC8 (session persistence).
 *
 * Features:
 * - Reads filters from URL query params on mount
 * - Falls back to localStorage if URL is empty (AC8)
 * - URL has priority over localStorage (AC6)
 * - Updates URL when filters change (replace mode, no history push)
 * - Saves filters to localStorage for session persistence
 * - Supports: engine, environment, tags (comma-separated), status, from_date, to_date, days
 * - Returns [filters, setFilters] similar to useState
 */

import { useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router';
import type { DashboardFilters, DashboardFilterStatus } from '../types/api';

const STORAGE_KEY = 'dashboard_filters';

/**
 * Parse filters from URL search params.
 */
function parseFiltersFromUrl(searchParams: URLSearchParams): DashboardFilters {
  const filters: DashboardFilters = {};

  const engine = searchParams.get('engine');
  if (engine) filters.engine = engine;

  const environment = searchParams.get('environment');
  if (environment) filters.environment = environment;

  const tags = searchParams.get('tags');
  if (tags) {
    const tagList = tags.split(',').filter(Boolean);
    if (tagList.length > 0) filters.tags = tagList;
  }

  const status = searchParams.get('status');
  if (status) filters.status = status as DashboardFilterStatus;

  const fromDate = searchParams.get('from_date');
  if (fromDate) filters.fromDate = fromDate;

  const toDate = searchParams.get('to_date');
  if (toDate) filters.toDate = toDate;

  const days = searchParams.get('days');
  if (days) {
    const parsedDays = parseInt(days, 10);
    if (!Number.isNaN(parsedDays)) filters.days = parsedDays;
  }

  return filters;
}

/**
 * Build URLSearchParams from filters, omitting null/undefined/empty values.
 */
function buildSearchParams(filters: DashboardFilters): URLSearchParams {
  const params = new URLSearchParams();

  if (filters.engine) params.set('engine', filters.engine);
  if (filters.environment) params.set('environment', filters.environment);
  if (filters.tags && filters.tags.length > 0) {
    params.set('tags', filters.tags.join(','));
  }
  if (filters.status) params.set('status', filters.status);
  if (filters.fromDate) params.set('from_date', filters.fromDate);
  if (filters.toDate) params.set('to_date', filters.toDate);
  if (filters.days) params.set('days', filters.days.toString());

  return params;
}

/**
 * Load filters from localStorage (Story 8.4, AC8).
 */
function loadFromStorage(): DashboardFilters | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
}

/**
 * Save filters to localStorage (Story 8.4, AC8).
 */
function saveToStorage(filters: DashboardFilters): void {
  try {
    if (Object.keys(filters).length === 0) {
      localStorage.removeItem(STORAGE_KEY);
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
    }
  } catch {
    // Ignore storage errors (e.g., quota exceeded)
  }
}

/**
 * Check if filters object has any non-empty values.
 */
function hasFilters(filters: DashboardFilters): boolean {
  return (
    !!filters.engine ||
    !!filters.environment ||
    !!(filters.tags && filters.tags.length > 0) ||
    !!filters.status ||
    !!filters.fromDate ||
    !!filters.toDate ||
    !!filters.days
  );
}

/**
 * Hook to synchronize DashboardFilters with URL query parameters and localStorage.
 *
 * Priority order:
 * 1. URL query params (highest priority - for shareable links)
 * 2. localStorage (fallback - for session persistence)
 * 3. Empty filters (default)
 *
 * @returns [filters, setFilters] tuple
 *
 * @example
 * const [filters, setFilters] = useUrlFilters();
 * // URL: ?engine=aap&environment=prod
 * // filters = { engine: 'aap', environment: 'prod' }
 *
 * setFilters({ engine: 'terraform' });
 * // URL updated to: ?engine=terraform
 * // localStorage updated to: { engine: 'terraform' }
 */
export function useUrlFilters(): readonly [
  DashboardFilters,
  (newFilters: DashboardFilters) => void,
] {
  const [searchParams, setSearchParams] = useSearchParams();
  const initializedRef = useRef(false);

  // Parse filters from current URL
  const urlFilters = useMemo(
    () => parseFiltersFromUrl(searchParams),
    [searchParams],
  );

  // On first render, check if URL is empty and restore from localStorage
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    // If URL has no filters, try to restore from localStorage
    if (!hasFilters(urlFilters)) {
      const storedFilters = loadFromStorage();
      if (storedFilters && hasFilters(storedFilters)) {
        const newParams = buildSearchParams(storedFilters);
        setSearchParams(newParams, { replace: true });
      }
    }
  }, [urlFilters, setSearchParams]);

  // Update URL and localStorage when filters change
  const setFilters = useCallback(
    (newFilters: DashboardFilters) => {
      const newParams = buildSearchParams(newFilters);
      setSearchParams(newParams, { replace: true });
      saveToStorage(newFilters);
    },
    [setSearchParams],
  );

  // Sync localStorage with URL filters (save when filters exist, clear when empty)
  useEffect(() => {
    if (hasFilters(urlFilters)) {
      saveToStorage(urlFilters);
    } else {
      // Clear localStorage when URL has no filters (user navigated to clean URL)
      saveToStorage({});
    }
  }, [urlFilters]);

  return [urlFilters, setFilters] as const;
}
