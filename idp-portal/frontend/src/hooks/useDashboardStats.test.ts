/**
 * Tests pour useDashboardReportingStats et useAdminPlatformStats (Story 71.1, AC6/AC7).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useDashboardReportingStats, useAdminPlatformStats } from './useDashboardStats';
import * as dashboardService from '../services/dashboard_service';
import { ApiError } from '../services/api_client';

vi.mock('../services/dashboard_service');
vi.mock('../services/logger', () => ({ default: { error: vi.fn(), warn: vi.fn(), debug: vi.fn() } }));
vi.mock('../services/api_client', () => ({
  ApiError: class ApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

describe('useDashboardReportingStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardService.fetchStatsByTechnology).mockResolvedValue([]);
    vi.mocked(dashboardService.fetchStatsByEnvironment).mockResolvedValue([]);
    vi.mocked(dashboardService.fetchTimeSeries).mockResolvedValue([]);
    vi.mocked(dashboardService.fetchFilterOptions).mockResolvedValue({ technologies: [], environments: [], statuses: [] } as never);
  });

  it('charge les stats au montage', async () => {
    const filters = { days: 14 };
    const { result } = renderHook(() => useDashboardReportingStats(filters));

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBeNull();
    expect(dashboardService.fetchStatsByTechnology).toHaveBeenCalledWith(filters);
    expect(dashboardService.fetchStatsByEnvironment).toHaveBeenCalledWith(filters);
    expect(dashboardService.fetchTimeSeries).toHaveBeenCalledWith(filters);
  });

  it('gère les erreurs de chargement', async () => {
    vi.mocked(dashboardService.fetchStatsByTechnology).mockRejectedValue(new Error('Network'));

    const filters = { days: 14 };
    const { result } = renderHook(() => useDashboardReportingStats(filters));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe('Network');
  });

  it('compare appelle fetchComparison', async () => {
    const mockResult = { metrics: [] };
    vi.mocked(dashboardService.fetchComparison).mockResolvedValue(mockResult as never);

    const filters = { days: 14 };
    const { result } = renderHook(() => useDashboardReportingStats(filters));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const comparisonResult = await result.current.compare({ dimension: 'technology', value1: 'a', value2: 'b' } as never);
    expect(comparisonResult).toEqual(mockResult);
  });
});

describe('useAdminPlatformStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dashboardService.fetchStatsCatalogue).mockResolvedValue({
      by_status: [{ status: 'published', count: 5 }],
      by_item_type: [{ item_type: 'workflow', count: 3 }],
      evolution: [],
    } as never);
    vi.mocked(dashboardService.fetchStatsAdoption).mockResolvedValue({
      active_users_by_profile: [{ profile: 'admin', user_count: 10 }],
      executions_by_profile: [],
    } as never);
  });

  it('charge catalogue et adoption', async () => {
    const { result } = renderHook(() => useAdminPlatformStats({ days: 14 }));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.catalogueData).not.toBeNull();
    expect(result.current.adoptionData).not.toBeNull();
    expect(result.current.catalogueForbidden).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('gère 403 catalogue silencieusement', async () => {
    const err403 = new ApiError('Forbidden', 403);
    vi.mocked(dashboardService.fetchStatsCatalogue).mockRejectedValue(err403);

    const { result } = renderHook(() => useAdminPlatformStats({ days: 14 }));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.catalogueForbidden).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('gère erreur non-403 catalogue', async () => {
    vi.mocked(dashboardService.fetchStatsCatalogue).mockRejectedValue(new Error('Server error'));

    const { result } = renderHook(() => useAdminPlatformStats({ days: 14 }));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.catalogueForbidden).toBe(false);
    expect(result.current.error).toBe('Server error');
  });
});
