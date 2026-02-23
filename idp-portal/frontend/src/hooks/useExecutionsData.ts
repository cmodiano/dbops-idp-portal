/**
 * useExecutionsData - Hook for managing executions data fetching and state
 *
 * Story 26.4 - AC6: Extracted from ExecutionsPage.tsx to reduce orchestrator to <400 LOC.
 * Handles listing executions, stats, time series, pending approvals, and integration icons.
 *
 * When the list contains running executions (RUNNING, SUBMITTED, PENDING_APPROVAL),
 * the hook polls every POLL_INTERVAL_MS so the view updates when status changes (e.g. "En cours" → "Terminée").
 * When there are no running executions, it still polls at BACKGROUND_POLL_INTERVAL_MS so new executions
 * triggered by other users eventually appear in the list.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  listExecutions,
  listPendingApprovals,
  fetchExecutionStats,
  fetchExecutionTimeSeries,
} from '../services/execution_service';
import { getIntegrations } from '../services/integrations_service';
import type { IntegrationIconsMap } from '../utils/executionRenderers';
import type {
  ExecutionResponse,
  ExecutionScope,
  ExecutionFilters,
  DashboardStats,
  DashboardTimeSeriesPoint,
  ExecutionStatusType,
} from '../types/api';
import logger from '../services/logger';

const PAGE_SIZE = 25;

/** Statuses that indicate an execution is still in progress; list should poll while any of these are present. */
const RUNNING_STATUSES: ExecutionStatusType[] = ['RUNNING', 'SUBMITTED', 'PENDING_APPROVAL'];

const POLL_INTERVAL_MS = 4000;
/** Slower interval when no running executions, so new executions from other users appear in the list. */
const BACKGROUND_POLL_INTERVAL_MS = 30000;

export interface UseExecutionsDataReturn {
  // Executions
  executions: ExecutionResponse[];
  loading: boolean;
  error: string | null;
  currentPage: number;
  setCurrentPage: (page: number) => void;
  totalCount: number;
  sortField: string;
  setSortField: (field: string) => void;
  sortOrder: 'ascend' | 'descend';
  setSortOrder: (order: 'ascend' | 'descend') => void;
  // Scope
  activeScope: ExecutionScope;
  setActiveScope: (scope: ExecutionScope) => void;
  userHasChosenScope: React.MutableRefObject<boolean>;
  // Stats
  statsData: DashboardStats | null;
  statsLoading: boolean;
  timeSeriesData: DashboardTimeSeriesPoint[];
  timeSeriesLoading: boolean;
  // Pending approvals
  pendingApprovals: ExecutionResponse[];
  pendingApprovalsLoading: boolean;
  loadPendingApprovals: () => Promise<void>;
  // Integration icons
  integrationIconsMap: IntegrationIconsMap | null;
  // Refs for stale closure prevention (Story 22.14)
  isRefreshingRef: React.MutableRefObject<boolean>;
  refetchCurrentState: () => Promise<void>;
  // Computed
  PAGE_SIZE: number;
}

export const useExecutionsData = (
  filters: ExecutionFilters,
  canApprove: boolean,
): UseExecutionsDataReturn => {
  const [integrationIconsMap, setIntegrationIconsMap] = useState<IntegrationIconsMap | null>(null);
  const [executions, setExecutions] = useState<ExecutionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend');
  const [activeScope, setActiveScope] = useState<ExecutionScope>('all');
  const userHasChosenScope = useRef(false);

  const [timeSeriesData, setTimeSeriesData] = useState<DashboardTimeSeriesPoint[]>([]);
  const [timeSeriesLoading, setTimeSeriesLoading] = useState(true);
  const [pendingApprovals, setPendingApprovals] = useState<ExecutionResponse[]>([]);
  const [pendingApprovalsLoading, setPendingApprovalsLoading] = useState(false);
  const [statsData, setStatsData] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Stale closure refs (Story 22.14)
  const currentPageRef = useRef(currentPage);
  const activeScopeRef = useRef(activeScope);
  const isRefreshingRef = useRef(false);

  useEffect(() => { currentPageRef.current = currentPage; }, [currentPage]);
  useEffect(() => { activeScopeRef.current = activeScope; }, [activeScope]);

  // Fetch executions
  const fetchData = useCallback(async (page: number, scope: ExecutionScope) => {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * PAGE_SIZE;
      const result = await listExecutions(PAGE_SIZE, offset, scope, filters);
      setExecutions(result.data);
      setTotalCount(result.pagination.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => { fetchData(currentPage, activeScope); }, [currentPage, activeScope, fetchData]);
  useEffect(() => { setCurrentPage(1); }, [filters]);

  const refetchCurrentState = useCallback(() => {
    return fetchData(currentPageRef.current, activeScopeRef.current);
  }, [fetchData]);

  // Silent refetch: update list + stats + time series without toggling loading (for polling)
  const refetchSilent = useCallback(async () => {
    const page = currentPageRef.current;
    const scope = activeScopeRef.current;
    const offset = (page - 1) * PAGE_SIZE;
    try {
      const [listResult, stats, timeSeries] = await Promise.all([
        listExecutions(PAGE_SIZE, offset, scope, filters),
        fetchExecutionStats(scope, filters),
        fetchExecutionTimeSeries(scope, filters),
      ]);
      setExecutions(listResult.data);
      setTotalCount(listResult.pagination.total);
      setStatsData(stats);
      setTimeSeriesData(timeSeries);
    } catch (err) {
      logger.error('Executions poll refetch failed', { error: err instanceof Error ? err.message : String(err) });
    }
  }, [filters]);

  // Poll so the list stays up to date: fast when any execution is running, slower otherwise (e.g. new executions from other users)
  useEffect(() => {
    const hasRunning = executions.some((e) => RUNNING_STATUSES.includes(e.status));
    const intervalMs = hasRunning ? POLL_INTERVAL_MS : BACKGROUND_POLL_INTERVAL_MS;

    const intervalId = setInterval(() => {
      refetchSilent();
    }, intervalMs);

    return () => clearInterval(intervalId);
  }, [executions, refetchSilent]);

  // Time series (Story 9.10)
  useEffect(() => {
    async function loadTimeSeries() {
      setTimeSeriesLoading(true);
      try {
        const data = await fetchExecutionTimeSeries(activeScope, filters);
        setTimeSeriesData(data);
      } catch (err) {
        logger.error('Erreur chargement timeseries', { error: err instanceof Error ? err.message : String(err) });
        setTimeSeriesData([]);
      } finally {
        setTimeSeriesLoading(false);
      }
    }
    loadTimeSeries();
  }, [activeScope, filters]);

  // Pending approvals (Story 8.8)
  const loadPendingApprovals = useCallback(async () => {
    if (!canApprove) return;
    setPendingApprovalsLoading(true);
    try {
      const response = await listPendingApprovals(50, 0);
      setPendingApprovals(response.data);
    } catch {
      setPendingApprovals([]);
    } finally {
      setPendingApprovalsLoading(false);
    }
  }, [canApprove]);

  useEffect(() => { loadPendingApprovals(); }, [loadPendingApprovals]);

  // Integration icons
  useEffect(() => {
    let cancelled = false;
    getIntegrations()
      .then((list) => {
        if (cancelled) return;
        const map: IntegrationIconsMap = {};
        const typeToPlatform: Record<string, string> = {
          aap: 'AAP', terraform: 'Terraform', azuredevops: 'Azure DevOps', github_actions: 'GitHub Actions',
        };
        for (const i of list) {
          if (i.name) map[i.name] = i.icon ?? null;
          if (i.type) {
            map[i.type] = i.icon ?? null;
            const platform = typeToPlatform[i.type.toLowerCase()];
            if (platform) map[platform] = i.icon ?? null;
          }
        }
        setIntegrationIconsMap(map);
      })
      .catch(() => { if (!cancelled) setIntegrationIconsMap(null); });
    return () => { cancelled = true; };
  }, []);

  // Stats (Story 9.4)
  useEffect(() => {
    async function loadStats() {
      setStatsLoading(true);
      try {
        const stats = await fetchExecutionStats(activeScope, filters);
        setStatsData(stats);
      } catch (err) {
        logger.error('Erreur chargement stats', { error: err instanceof Error ? err.message : String(err) });
        setStatsData({ executions_jour: 0, taux_succes_pct: 0, executions_en_cours: 0, executions_en_erreur: 0 });
      } finally {
        setStatsLoading(false);
      }
    }
    loadStats();
  }, [activeScope, filters]);

  return {
    executions, loading, error, currentPage, setCurrentPage, totalCount,
    sortField, setSortField, sortOrder, setSortOrder,
    activeScope, setActiveScope, userHasChosenScope,
    statsData, statsLoading, timeSeriesData, timeSeriesLoading,
    pendingApprovals, pendingApprovalsLoading, loadPendingApprovals,
    integrationIconsMap,
    isRefreshingRef, refetchCurrentState,
    PAGE_SIZE,
  };
};
