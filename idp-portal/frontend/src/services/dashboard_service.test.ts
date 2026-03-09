/**
 * Tests for dashboard_service (Story 66.10 - AC#3).
 *
 * Covers: fetchStats, fetchTimeSeries, logique date range (custom vs days),
 * fetchComparison, downloadBlob, exports CSV/PDF.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as dashboardService from './dashboard_service';
import * as apiClient from './api_client';

vi.mock('./api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchBlob: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

describe('dashboard_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  // =========================================================================
  // fetchStats
  // =========================================================================

  describe('fetchStats', () => {
    it('calls GET /dashboard/stats with default days=14', async () => {
      const mockStats = {
        executions_jour: 5,
        taux_succes_pct: 90,
        executions_en_cours: 2,
        executions_en_erreur: 1,
      };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockStats);

      const result = await dashboardService.fetchStats();

      expect(apiClient.apiFetch).toHaveBeenCalledWith(
        expect.stringContaining('/dashboard/stats'),
      );
      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('days=14');
      expect(result).toEqual(mockStats);
    });

    it('calls GET /dashboard/stats with custom days filter', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStats({ days: 30 });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('days=30');
    });

    it('calls GET /dashboard/stats with engine and environment filters', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStats({ engine: 'aap', environment: 'prod' });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('engine=aap');
      expect(url).toContain('environment=prod');
    });

    it('sends tags as multiple query params', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStats({ tags: ['oracle', 'postgres'] });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('tags=oracle');
      expect(url).toContain('tags=postgres');
    });

    it('sends status filter when provided', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStats({ status: 'FAILED' });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('status=failed');
    });
  });

  // =========================================================================
  // Date range logic — custom_dates override days
  // =========================================================================

  describe('Date range logic (buildFilterParams)', () => {
    it('does NOT send days when fromDate and toDate are both set', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStats({
        fromDate: '2026-01-01',
        toDate: '2026-01-31',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('from_date=2026-01-01');
      expect(url).toContain('to_date=2026-01-31');
      expect(url).not.toContain('days=');
    });

    it('sends days when only fromDate is set (partial custom date range)', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStats({
        days: 7,
        fromDate: '2026-01-01',
        // toDate not set — not a complete custom date range
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      // Without toDate, hasCustomDateRange is false → days IS sent
      expect(url).toContain('days=7');
    });

    it('custom date range overrides days even when days is explicitly set', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStats({
        days: 30,
        fromDate: '2026-01-01',
        toDate: '2026-01-31',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).not.toContain('days=');
      expect(url).toContain('from_date=2026-01-01');
      expect(url).toContain('to_date=2026-01-31');
    });
  });

  // =========================================================================
  // fetchTimeSeries
  // =========================================================================

  describe('fetchTimeSeries', () => {
    it('calls GET /dashboard/timeseries with default days=14', async () => {
      const mockData = [{ date: '2026-01-01', success: 10, failed: 2 }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockData);

      const result = await dashboardService.fetchTimeSeries();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/timeseries');
      expect(url).toContain('days=14');
      expect(result).toEqual(mockData);
    });

    it('calls with custom days filter', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await dashboardService.fetchTimeSeries({ days: 7 });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('days=7');
    });

    it('does not send days when custom date range is provided', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await dashboardService.fetchTimeSeries({
        fromDate: '2026-02-01',
        toDate: '2026-02-28',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).not.toContain('days=');
      expect(url).toContain('from_date=2026-02-01');
    });
  });

  // =========================================================================
  // fetchComparison
  // =========================================================================

  describe('fetchComparison', () => {
    it('calls GET /dashboard/compare with technology dimension', async () => {
      const mockResult = {
        value1_stats: { total: 10, success_rate: 90 },
        value2_stats: { total: 15, success_rate: 80 },
        deltas: {},
      };
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockResult);

      const result = await dashboardService.fetchComparison({
        dimension: 'technology',
        value1: 'aap',
        value2: 'terraform',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/compare');
      expect(url).toContain('dimension=technology');
      expect(url).toContain('value1=aap');
      expect(url).toContain('value2=terraform');
      expect(result).toEqual(mockResult);
    });

    it('calls GET /dashboard/compare with environment dimension', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchComparison({
        dimension: 'environment',
        value1: 'dev',
        value2: 'prod',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('dimension=environment');
      expect(url).toContain('value1=dev');
      expect(url).toContain('value2=prod');
    });

    it('calls GET /dashboard/compare with period dimension and period dates', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchComparison({
        dimension: 'period',
        value1: 'week1',
        value2: 'week2',
        period1Start: '2026-01-01',
        period1End: '2026-01-07',
        period2Start: '2026-01-08',
        period2End: '2026-01-14',
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('dimension=period');
      expect(url).toContain('period1_start=2026-01-01');
      expect(url).toContain('period1_end=2026-01-07');
      expect(url).toContain('period2_start=2026-01-08');
      expect(url).toContain('period2_end=2026-01-14');
    });

    it('sends metrics as multiple query params', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchComparison({
        dimension: 'technology',
        value1: 'aap',
        value2: 'terraform',
        metrics: ['execution_count', 'success_rate'],
      });

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('metrics=execution_count');
      expect(url).toContain('metrics=success_rate');
    });
  });

  // =========================================================================
  // downloadBlob (via exportDashboardCSV / exportDashboardPDF)
  // =========================================================================

  describe('downloadBlob (via export functions)', () => {
    let createObjectURLMock: ReturnType<typeof vi.fn>;
    let revokeObjectURLMock: ReturnType<typeof vi.fn>;
    let appendChildMock: ReturnType<typeof vi.fn>;
    let removeChildMock: ReturnType<typeof vi.fn>;
    let clickMock: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      createObjectURLMock = vi.fn().mockReturnValue('blob:http://localhost/test-url');
      revokeObjectURLMock = vi.fn();
      clickMock = vi.fn();
      appendChildMock = vi.fn();
      removeChildMock = vi.fn();

      window.URL.createObjectURL = createObjectURLMock as typeof URL.createObjectURL;
      window.URL.revokeObjectURL = revokeObjectURLMock as typeof URL.revokeObjectURL;

      const mockAnchor = {
        href: '',
        download: '',
        click: clickMock,
      } as unknown as HTMLAnchorElement;

      vi.spyOn(document, 'createElement').mockReturnValue(mockAnchor);
      vi.spyOn(document.body, 'appendChild').mockImplementation(appendChildMock as typeof document.body.appendChild);
      vi.spyOn(document.body, 'removeChild').mockImplementation(removeChildMock as typeof document.body.removeChild);
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('exportDashboardCSV: calls apiFetchBlob and triggers download with .csv extension', async () => {
      const mockBlob = new Blob(['col1,col2'], { type: 'text/csv' });
      vi.mocked(apiClient.apiFetchBlob).mockResolvedValue(mockBlob);

      await dashboardService.exportDashboardCSV();

      expect(apiClient.apiFetchBlob).toHaveBeenCalledWith(
        expect.stringContaining('/dashboard/export/csv'),
      );
      expect(createObjectURLMock).toHaveBeenCalledWith(mockBlob);
      expect(clickMock).toHaveBeenCalled();
      expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:http://localhost/test-url');

      // Verify the download filename contains .csv
      const anchorElement = vi.mocked(document.createElement).mock.results[0]?.value as HTMLAnchorElement;
      expect(anchorElement?.download).toMatch(/dashboard-report-.+\.csv$/);
    });

    it('exportDashboardPDF: calls apiFetchBlob and triggers download with .pdf extension', async () => {
      const mockBlob = new Blob(['%PDF'], { type: 'application/pdf' });
      vi.mocked(apiClient.apiFetchBlob).mockResolvedValue(mockBlob);

      await dashboardService.exportDashboardPDF();

      expect(apiClient.apiFetchBlob).toHaveBeenCalledWith(
        expect.stringContaining('/dashboard/export/pdf'),
      );

      const anchorElement = vi.mocked(document.createElement).mock.results[0]?.value as HTMLAnchorElement;
      expect(anchorElement?.download).toMatch(/dashboard-report-.+\.pdf$/);
    });

    it('exportDashboardCSV: filename includes ISO timestamp format', async () => {
      vi.mocked(apiClient.apiFetchBlob).mockResolvedValue(new Blob([]));

      await dashboardService.exportDashboardCSV();

      const anchorElement = vi.mocked(document.createElement).mock.results[0]?.value as HTMLAnchorElement;
      // Format: dashboard-report-YYYY-MM-DD-HH-MM.csv
      expect(anchorElement?.download).toMatch(
        /^dashboard-report-\d{4}-\d{2}-\d{2}-\d{2}-\d{2}\.csv$/,
      );
    });

    it('exportDashboardCSV: appends and removes link from DOM', async () => {
      vi.mocked(apiClient.apiFetchBlob).mockResolvedValue(new Blob([]));

      await dashboardService.exportDashboardCSV();

      expect(appendChildMock).toHaveBeenCalled();
      expect(removeChildMock).toHaveBeenCalled();
    });

    it('exportDashboardCSV: passes filters to query string', async () => {
      vi.mocked(apiClient.apiFetchBlob).mockResolvedValue(new Blob([]));

      await dashboardService.exportDashboardCSV({ days: 7, engine: 'aap' });

      const url = vi.mocked(apiClient.apiFetchBlob).mock.calls[0][0] as string;
      expect(url).toContain('days=7');
      expect(url).toContain('engine=aap');
    });

    it('exportDashboardPDF: passes filters to query string', async () => {
      vi.mocked(apiClient.apiFetchBlob).mockResolvedValue(new Blob([]));

      await dashboardService.exportDashboardPDF({
        fromDate: '2026-01-01',
        toDate: '2026-01-31',
      });

      const url = vi.mocked(apiClient.apiFetchBlob).mock.calls[0][0] as string;
      expect(url).toContain('from_date=2026-01-01');
      expect(url).toContain('to_date=2026-01-31');
      // Custom date range: days should NOT be in URL
      expect(url).not.toContain('days=');
    });
  });

  // =========================================================================
  // Admin stats functions (AC coverage)
  // =========================================================================

  describe('fetchStatsCatalogue', () => {
    it('calls GET /dashboard/stats-catalogue with default days=30', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStatsCatalogue();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/stats-catalogue');
      expect(url).toContain('days=30');
    });
  });

  describe('fetchStatsAdoption', () => {
    it('calls GET /dashboard/stats-adoption with default days=14', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStatsAdoption();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/stats-adoption');
      expect(url).toContain('days=14');
    });
  });

  describe('fetchStatsOperations', () => {
    it('calls GET /dashboard/stats-operations with default days=14', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStatsOperations();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/stats-operations');
      expect(url).toContain('days=14');
    });
  });

  describe('fetchStatsApprobations', () => {
    it('calls GET /dashboard/stats-approbations with default days=14', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStatsApprobations();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/stats-approbations');
      expect(url).toContain('days=14');
    });
  });

  describe('fetchStatsPlanifiees', () => {
    it('calls GET /dashboard/stats-planifiees with default days=14', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue({});

      await dashboardService.fetchStatsPlanifiees();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/stats-planifiees');
      expect(url).toContain('days=14');
    });
  });

  // =========================================================================
  // Other public functions
  // =========================================================================

  describe('fetchRecent', () => {
    it('calls GET /dashboard/recent', async () => {
      const mockRecent = [{ id: 1, action: 'test', status: 'success' }];
      vi.mocked(apiClient.apiFetch).mockResolvedValue(mockRecent);

      const result = await dashboardService.fetchRecent();

      expect(apiClient.apiFetch).toHaveBeenCalledWith('/dashboard/recent');
      expect(result).toEqual(mockRecent);
    });
  });

  describe('fetchStatsByTechnology', () => {
    it('calls GET /dashboard/stats-by-technology', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await dashboardService.fetchStatsByTechnology();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/stats-by-technology');
    });
  });

  describe('fetchStatsByEnvironment', () => {
    it('calls GET /dashboard/stats-by-environment', async () => {
      vi.mocked(apiClient.apiFetch).mockResolvedValue([]);

      await dashboardService.fetchStatsByEnvironment();

      const url = vi.mocked(apiClient.apiFetch).mock.calls[0][0] as string;
      expect(url).toContain('/dashboard/stats-by-environment');
    });
  });

  describe('fetchFilterOptions', () => {
    it('calls apiFetchRaw for /dashboard/filter-options (unwrapped response)', async () => {
      const mockOptions = { engines: ['aap'], environments: ['prod'], tags: [], statuses: [] };
      vi.mocked(apiClient.apiFetchRaw).mockResolvedValue(mockOptions);

      const result = await dashboardService.fetchFilterOptions();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/dashboard/filter-options');
      expect(result).toEqual(mockOptions);
    });
  });
});
