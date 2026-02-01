/**
 * Dashboard service (Story 5.1, Task 2.1; Story 8.3).
 *
 * Provides functions to fetch dashboard statistics and recent executions.
 */

import { apiFetch } from './api_client';
import type {
  DashboardStats,
  DashboardRecentExecution,
  DashboardTimeSeriesPoint,
  TechnologyStats,
  EnvironmentStats,
} from '../types/api';

/**
 * Fetch dashboard statistics (Story 5.1, AC1, AC4; Story 8.3, AC6).
 *
 * Returns aggregated metrics:
 * - executions_jour: Executions today (always current day)
 * - taux_succes_pct: Success rate % over selected period
 * - executions_en_cours: Running executions
 * - executions_en_erreur: Failed executions in selected period
 *
 * @param days Period filter in days (7, 14, 30, 90). Default 14.
 * @returns DashboardStats
 */
export async function fetchStats(days: number = 14): Promise<DashboardStats> {
  return apiFetch<DashboardStats>(`/dashboard/stats?days=${days}`);
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

/**
 * Fetch execution stats grouped by database engine (Story 8.3, AC3, AC7).
 *
 * Returns executions aggregated by engine with count and success rate.
 *
 * @param days Period filter in days (7, 14, 30, 90). Default 14.
 * @returns Array of TechnologyStats
 */
export async function fetchStatsByTechnology(
  days: number = 14,
): Promise<TechnologyStats[]> {
  return apiFetch<TechnologyStats[]>(`/dashboard/stats-by-technology?days=${days}`);
}

/**
 * Fetch execution stats grouped by environment (Story 8.3, AC4, AC7).
 *
 * Returns executions aggregated by environment with count and success rate.
 * Results are ordered: dev, staging, prod, then alphabetical.
 *
 * @param days Period filter in days (7, 14, 30, 90). Default 14.
 * @returns Array of EnvironmentStats
 */
export async function fetchStatsByEnvironment(
  days: number = 14,
): Promise<EnvironmentStats[]> {
  return apiFetch<EnvironmentStats[]>(`/dashboard/stats-by-environment?days=${days}`);
}
