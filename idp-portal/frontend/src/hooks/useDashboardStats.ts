/**
 * useDashboardReportingStats — Encapsulation DIP des fonctions dashboard pour ReportingDashboard.
 * useAdminPlatformStats — Encapsulation DIP pour AdminPlatformSection.
 * Story 71.1, AC6/AC7.
 */

import { useState, useEffect, useCallback } from 'react';
import {
  fetchStatsByTechnology,
  fetchStatsByEnvironment,
  fetchTimeSeries,
  fetchFilterOptions,
  fetchComparison,
  fetchStatsCatalogue,
  fetchStatsAdoption,
} from '../services/dashboard_service';
import type {
  DashboardFilters,
  TechnologyStats,
  EnvironmentStats,
  DashboardTimeSeriesPoint,
  FilterOptions,
  ComparisonResult,
  ComparisonFilters,
  StatsCatalogueData,
  StatsAdoptionData,
} from '../types/api';
import { ApiError } from '../services/api_client';
import { normalizeEnvironmentStats } from '../utils/environmentHelpers';
import logger from '../services/logger';

export interface UseDashboardReportingStatsReturn {
  techStats: TechnologyStats[];
  envStats: EnvironmentStats[];
  timeSeries: DashboardTimeSeriesPoint[];
  filterOptions: FilterOptions | null;
  loading: boolean;
  error: string | null;
  setError: (error: string | null) => void;
  compare: (filters: ComparisonFilters) => Promise<ComparisonResult>;
}

export function useDashboardReportingStats(
  filters: DashboardFilters,
): UseDashboardReportingStatsReturn {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [techStats, setTechStats] = useState<TechnologyStats[]>([]);
  const [envStats, setEnvStats] = useState<EnvironmentStats[]>([]);
  const [timeSeries, setTimeSeries] = useState<DashboardTimeSeriesPoint[]>([]);

  const filtersKey = JSON.stringify(filters);

  // Load filter options on mount
  useEffect(() => {
    fetchFilterOptions()
      .then(setFilterOptions)
      .catch((err: unknown) => {
        logger.warn('reporting_filter_options_error', {
          error: err instanceof Error ? err.message : String(err),
          fallback: 'default_options',
        });
      });
  }, []);

  // Load dashboard data when filters change
  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setError(null);
      try {
        const [techData, envData, timeData] = await Promise.all([
          fetchStatsByTechnology(filters),
          fetchStatsByEnvironment(filters),
          fetchTimeSeries(filters),
        ]);
        if (cancelled) return;
        setTechStats(techData);
        setEnvStats(normalizeEnvironmentStats(envData));
        setTimeSeries(timeData);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Erreur lors du chargement');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadData();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

  const compare = useCallback(async (comparisonFilters: ComparisonFilters): Promise<ComparisonResult> => {
    return fetchComparison(comparisonFilters);
  }, []);

  return { techStats, envStats, timeSeries, filterOptions, loading, error, setError, compare };
}

export interface UseAdminPlatformStatsReturn {
  catalogueData: StatsCatalogueData | null;
  adoptionData: StatsAdoptionData | null;
  loading: boolean;
  error: string | null;
  setError: (error: string | null) => void;
  catalogueForbidden: boolean;
}

export function useAdminPlatformStats(filters: DashboardFilters): UseAdminPlatformStatsReturn {
  const [catalogueData, setCatalogueData] = useState<StatsCatalogueData | null>(null);
  const [adoptionData, setAdoptionData] = useState<StatsAdoptionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [catalogueForbidden, setCatalogueForbidden] = useState(false);

  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setError(null);
      setCatalogueForbidden(false);

      const [catalogueResult, adoptionResult] = await Promise.allSettled([
        fetchStatsCatalogue(filters),
        fetchStatsAdoption(filters),
      ]);

      if (cancelled) return;

      if (catalogueResult.status === 'fulfilled') {
        setCatalogueData(catalogueResult.value);
      } else {
        const err = catalogueResult.reason;
        if (err instanceof ApiError && err.status === 403) {
          setCatalogueForbidden(true);
        } else {
          setError(err instanceof Error ? err.message : 'Erreur de chargement');
        }
      }

      if (adoptionResult.status === 'fulfilled') {
        setAdoptionData(adoptionResult.value);
      } else {
        const err = adoptionResult.reason;
        setError((prev) =>
          prev ? prev : err instanceof Error ? err.message : 'Erreur de chargement'
        );
      }

      setLoading(false);
    }

    loadData();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersKey]);

  return { catalogueData, adoptionData, loading, error, setError, catalogueForbidden };
}
