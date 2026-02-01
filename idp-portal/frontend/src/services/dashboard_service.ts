/**
 * Dashboard service (Story 5.1, Task 2.1).
 *
 * Provides functions to fetch dashboard statistics and recent executions.
 */

import { apiFetch } from './api_client';
import type {
  DashboardStats,
  DashboardRecentExecution,
  DashboardTimeSeriesPoint,
} from '../types/api';

/**
 * Fetch dashboard statistics (Story 5.1, AC1, AC4).
 *
 * Returns aggregated metrics:
 * - executions_jour: Executions today
 * - taux_succes_pct: Success rate %
 * - executions_en_cours: Running executions
 * - executions_en_erreur: Failed executions (24h)
 *
 * @returns DashboardStats
 */
export async function fetchStats(): Promise<DashboardStats> {
  return apiFetch<DashboardStats>('/dashboard/stats');
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
 * Fetch executions time series for line chart (last N days).
 *
 * @param days Number of days (default 14)
 * @returns Array of { date, success, failed } per day
 */
export async function fetchTimeSeries(
  days: number = 14,
): Promise<DashboardTimeSeriesPoint[]> {
  return apiFetch<DashboardTimeSeriesPoint[]>(`/dashboard/timeseries?days=${days}`);
}
