/**
 * Dashboard service (Story 5.1, Task 2.1; Story 8.3; Story 8.4; Story 8.5; Story 8.6).
 *
 * Provides functions to fetch dashboard statistics and recent executions.
 */

import { apiFetch, apiFetchBlob, apiFetchRaw } from './api_client';
import type {
  DashboardStats,
  DashboardRecentExecution,
  DashboardTimeSeriesPoint,
  TechnologyStats,
  EnvironmentStats,
  DashboardFilters,
  FilterOptions,
  ComparisonFilters,
  ComparisonResult,
} from '../types/api';

/**
 * Build query string from filters, ignoring null/undefined/empty values (Story 8.4, Task 9.5).
 * Note: When fromDate/toDate are set, days is NOT sent (custom date range takes priority).
 */
function buildFilterParams(filters: DashboardFilters = {}): URLSearchParams {
  const params = new URLSearchParams();

  // Only send days if NOT using custom date range (fromDate/toDate take priority)
  const hasCustomDateRange = !!(filters.fromDate && filters.toDate);
  if (filters.days && !hasCustomDateRange) {
    params.set('days', filters.days.toString());
  }
  if (filters.engine) params.set('engine', filters.engine);
  if (filters.environment) params.set('environment', filters.environment);
  if (filters.status) params.set('status', filters.status);
  if (filters.fromDate) params.set('from_date', filters.fromDate);
  if (filters.toDate) params.set('to_date', filters.toDate);
  // Tags as multiple query params
  if (filters.tags && filters.tags.length > 0) {
    filters.tags.forEach((tag) => params.append('tags', tag));
  }

  return params;
}

/**
 * Fetch dashboard statistics (Story 5.1, AC1, AC4; Story 8.3, AC6; Story 8.4, AC7).
 *
 * Returns aggregated metrics:
 * - executions_jour: Executions today (always current day)
 * - taux_succes_pct: Success rate % over selected period
 * - executions_en_cours: Running executions
 * - executions_en_erreur: Failed executions in selected period
 *
 * @param filters Optional filters including days, engine, environment, tags, status, fromDate, toDate
 * @returns DashboardStats
 */
export async function fetchStats(filters: DashboardFilters = {}): Promise<DashboardStats> {
  const params = buildFilterParams({ days: 14, ...filters });
  return apiFetch<DashboardStats>(`/dashboard/stats?${params.toString()}`);
}

/**
 * Fetch recent executions for dashboard (Story 5.1, AC2, AC4).
 *
 * Returns the 10 most recent executions across all users (DBA/DBOPS visibility).
 *
 * @returns Array of DashboardRecentExecution
 */
export async function fetchRecent(): Promise<DashboardRecentExecution[]> {
  return apiFetch<DashboardRecentExecution[]>('/dashboard/recent');
}

/**
 * Fetch executions time series for line chart (Story 8.4, AC7).
 *
 * @param filters Optional filters including days, engine, environment, tags, status, fromDate, toDate
 * @returns Array of { date, success, failed } per day
 */
export async function fetchTimeSeries(
  filters: DashboardFilters = {},
): Promise<DashboardTimeSeriesPoint[]> {
  const params = buildFilterParams({ days: 14, ...filters });
  return apiFetch<DashboardTimeSeriesPoint[]>(`/dashboard/timeseries?${params.toString()}`);
}

/**
 * Fetch execution stats grouped by database engine (Story 8.3, AC3, AC7; Story 8.4, AC7).
 *
 * Returns executions aggregated by engine with count and success rate.
 * Note: engine filter is not applicable here since engine is the grouping key.
 *
 * @param filters Optional filters including days, environment, tags, status, fromDate, toDate
 * @returns Array of TechnologyStats
 */
export async function fetchStatsByTechnology(
  filters: DashboardFilters = {},
): Promise<TechnologyStats[]> {
  // Remove engine from filters since it's the grouping key
  const { engine: _, ...restFilters } = filters;
  const params = buildFilterParams({ days: 14, ...restFilters });
  return apiFetch<TechnologyStats[]>(`/dashboard/stats-by-technology?${params.toString()}`);
}

/**
 * Fetch execution stats grouped by environment (Story 8.3, AC4, AC7; Story 8.4, AC7).
 *
 * Returns executions aggregated by environment with count and success rate.
 * Results are ordered: dev, staging, prod, then alphabetical.
 * Note: environment filter is not applicable here since environment is the grouping key.
 *
 * @param filters Optional filters including days, engine, tags, status, fromDate, toDate
 * @returns Array of EnvironmentStats
 */
export async function fetchStatsByEnvironment(
  filters: DashboardFilters = {},
): Promise<EnvironmentStats[]> {
  // Remove environment from filters since it's the grouping key
  const { environment: _, ...restFilters } = filters;
  const params = buildFilterParams({ days: 14, ...restFilters });
  return apiFetch<EnvironmentStats[]>(`/dashboard/stats-by-environment?${params.toString()}`);
}

/**
 * Fetch available filter options (Story 8.4, Task 14).
 *
 * Returns distinct values for each filter type based on actual data.
 *
 * @returns FilterOptions with engines, environments, tags, statuses
 */
export async function fetchFilterOptions(): Promise<FilterOptions> {
  // Use apiFetchRaw because the API returns the object directly, not wrapped in .data
  return apiFetchRaw<FilterOptions>('/dashboard/filter-options');
}

/**
 * Trigger download of a blob with a given filename.
 * @internal
 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

/**
 * Extract filename from Content-Disposition header or use fallback.
 * Note: apiFetchBlob doesn't return headers, so we use a default pattern.
 * @internal
 */
function generateExportFilename(format: 'csv' | 'pdf'): string {
  const now = new Date();
  const timestamp = now.toISOString().slice(0, 16).replace('T', '-').replace(':', '-');
  return `dashboard-report-${timestamp}.${format}`;
}

/**
 * Export dashboard data as CSV (Story 8.5, AC2, AC6).
 * Triggers browser download.
 *
 * @param filters Optional filters to apply to export
 */
export async function exportDashboardCSV(filters: DashboardFilters = {}): Promise<void> {
  const params = buildFilterParams({ days: 14, ...filters });
  const queryString = params.toString();
  const url = `/dashboard/export/csv${queryString ? `?${queryString}` : ''}`;

  const blob = await apiFetchBlob(url);
  const filename = generateExportFilename('csv');
  downloadBlob(blob, filename);
}

/**
 * Export dashboard data as PDF (Story 8.5, AC3, AC7).
 * Triggers browser download.
 *
 * @param filters Optional filters to apply to export
 */
export async function exportDashboardPDF(filters: DashboardFilters = {}): Promise<void> {
  const params = buildFilterParams({ days: 14, ...filters });
  const queryString = params.toString();
  const url = `/dashboard/export/pdf${queryString ? `?${queryString}` : ''}`;

  const blob = await apiFetchBlob(url);
  const filename = generateExportFilename('pdf');
  downloadBlob(blob, filename);
}

// === Comparison Functions (Story 8.6) ===

/**
 * Build query parameters for comparison request (Story 8.6, Task 7.2).
 */
function buildComparisonParams(filters: ComparisonFilters): URLSearchParams {
  const params = new URLSearchParams();

  params.set('dimension', filters.dimension);
  params.set('value1', filters.value1);
  params.set('value2', filters.value2);

  if (filters.days) {
    params.set('days', filters.days.toString());
  }

  // Period dates for period dimension
  if (filters.period1Start) params.set('period1_start', filters.period1Start);
  if (filters.period1End) params.set('period1_end', filters.period1End);
  if (filters.period2Start) params.set('period2_start', filters.period2Start);
  if (filters.period2End) params.set('period2_end', filters.period2End);

  // Metrics as multiple query params
  if (filters.metrics && filters.metrics.length > 0) {
    filters.metrics.forEach((metric) => params.append('metrics', metric));
  }

  return params;
}

/**
 * Fetch comparison data between two values (Story 8.6, AC7).
 *
 * Compares execution metrics across dimensions:
 * - technology: Compare two database engines (e.g., AAP vs Terraform)
 * - environment: Compare two environments (e.g., dev vs prod)
 * - period: Compare two time periods (e.g., last week vs this week)
 *
 * @param filters Comparison filters with dimension, value1, value2, and optional period dates
 * @returns ComparisonResult with value1_stats, value2_stats, and deltas
 */
export async function fetchComparison(filters: ComparisonFilters): Promise<ComparisonResult> {
  const params = buildComparisonParams(filters);
  return apiFetch<ComparisonResult>(`/dashboard/compare?${params.toString()}`);
}
