/**
 * Execution dashboard API — stats, timeseries, tags.
 * Story 9.4; Story 9.10.
 */

import { apiFetch } from './api_client';
import { buildFilterParams } from './execution_core';
import type {
  ExecutionScope,
  ExecutionFilters,
  DashboardStats,
  DashboardTimeSeriesPoint,
} from '../types/api';

export async function fetchExecutionStats(
  scope: ExecutionScope = 'mine',
  filters?: ExecutionFilters
): Promise<DashboardStats> {
  const baseParams = `scope=${scope}`;
  const filterParams = buildFilterParams(filters);
  const queryString = filterParams ? `${baseParams}&${filterParams}` : baseParams;
  return apiFetch<DashboardStats>(`/executions/stats?${queryString}`);
}

export async function fetchExecutionTimeSeries(
  scope: ExecutionScope = 'mine',
  filters?: ExecutionFilters
): Promise<DashboardTimeSeriesPoint[]> {
  const baseParams = `scope=${scope}`;
  const filterParams = buildFilterParams(filters);
  const queryString = filterParams ? `${baseParams}&${filterParams}` : baseParams;
  return apiFetch<DashboardTimeSeriesPoint[]>(`/executions/timeseries?${queryString}`);
}

export async function fetchExecutionTags(): Promise<string[]> {
  return apiFetch<string[]>('/executions/tags');
}
