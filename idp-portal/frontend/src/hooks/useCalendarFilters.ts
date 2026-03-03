/**
 * useCalendarFilters - Hook for managing calendar filters with URL sync (Story 13.6, AC5).
 *
 * Provides:
 * - filters: Current filter state
 * - applyFilters: Update filters and sync to URL
 * - resetFilters: Clear all filters
 * - activeFilterCount: Number of active (non-default) filters
 *
 * AC5: Filters persist in URL query params for sharing and refresh
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router';
import type { ExecutionEnvironment } from '../types/api';
import type { ScheduledExecutionStatus } from '../types/api';

/** Calendar filter values (Story 13.6, AC4). */
export interface CalendarFilters {
  /** Filter by action ID. */
  action_id: number | null;
  /** Filter by environment (dev, staging, prod). */
  environment: ExecutionEnvironment | null;
  /** Filter by engine/technology. */
  engine: string | null;
  /** Filter by platform. */
  platform: string | null;
  /** Start date for date range filter (YYYY-MM-DD). */
  start_date: string | null;
  /** End date for date range filter (YYYY-MM-DD). */
  end_date: string | null;
  /** Filter by status: pending (en attente), executed (terminées), or null (toutes). */
  status: ScheduledExecutionStatus | null;
}

/** Default filters (no filtering applied). */
const DEFAULT_FILTERS: CalendarFilters = {
  action_id: null,
  environment: null,
  engine: null,
  platform: null,
  start_date: null,
  end_date: null,
  status: 'pending',
};

const VALID_STATUSES: ScheduledExecutionStatus[] = ['pending', 'executed', 'cancelled'];

/** Parse URL query params into CalendarFilters. */
function parseFiltersFromURL(search: string): CalendarFilters {
  const params = new URLSearchParams(search);
  const actionIdRaw = params.get('action_id');
  const actionId = actionIdRaw ? parseInt(actionIdRaw, 10) : null;
  const statusParam = params.get('status');
  let status: ScheduledExecutionStatus | null = 'pending';
  if (statusParam === 'all') status = null;
  else if (statusParam && VALID_STATUSES.includes(statusParam as ScheduledExecutionStatus))
    status = statusParam as ScheduledExecutionStatus;

  return {
    action_id: actionId != null && !Number.isNaN(actionId) ? actionId : null,
    environment: (params.get('environment') as ExecutionEnvironment) || null,
    engine: params.get('engine') || null,
    platform: params.get('platform') || null,
    start_date: params.get('start_date') || null,
    end_date: params.get('end_date') || null,
    status,
  };
}

/** Build URL query string from filters. */
function buildURLFromFilters(filters: CalendarFilters): string {
  const params = new URLSearchParams();

  if (filters.action_id) params.set('action_id', String(filters.action_id));
  if (filters.environment) params.set('environment', filters.environment);
  if (filters.engine) params.set('engine', filters.engine);
  if (filters.platform) params.set('platform', filters.platform);
  if (filters.start_date) params.set('start_date', filters.start_date);
  if (filters.end_date) params.set('end_date', filters.end_date);
  if (filters.status === null) params.set('status', 'all');
  else if (filters.status !== 'pending') params.set('status', filters.status);

  return params.toString();
}

/** Count number of active (non-null) filters. */
function countActiveFilters(filters: CalendarFilters): number {
  let count = 0;
  if (filters.action_id) count++;
  if (filters.environment) count++;
  if (filters.engine) count++;
  if (filters.platform) count++;
  if (filters.start_date || filters.end_date) count++;
  if (filters.status !== 'pending') count++;
  return count;
}

export interface UseCalendarFiltersResult {
  /** Current filter values. */
  filters: CalendarFilters;
  /** Apply new filters (updates URL). */
  applyFilters: (newFilters: CalendarFilters) => void;
  /** Reset all filters to defaults. */
  resetFilters: () => void;
  /** Number of active filters (for badge). */
  activeFilterCount: number;
  /** Whether any filter is active. */
  hasActiveFilters: boolean;
}

export function useCalendarFilters(): UseCalendarFiltersResult {
  const navigate = useNavigate();
  const location = useLocation();

  // Initialize filters from URL on mount
  const [filters, setFilters] = useState<CalendarFilters>(() =>
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
    (newFilters: CalendarFilters) => {
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

export default useCalendarFilters;
