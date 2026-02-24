/**
 * useExecutionsData - Hook for managing executions data fetching and state
 *
 * Story 26.4 - AC6: Extracted from ExecutionsPage.tsx to reduce orchestrator to <400 LOC.
 * Handles listing executions, stats, time series, pending approvals, and integration icons.
 * Story 36.2: Real-time WS sync for the actor's own active executions (useActorExecutionSync).
 * Story 36.3: Observer polling with Page Visibility API (see polling useEffect below).
 *
 * When the list contains running executions (RUNNING, SUBMITTED, PENDING_APPROVAL),
 * the hook polls every OBSERVER_POLL_INTERVAL_MS (10 s) so observers see status changes
 * (e.g. "En cours" → "Terminée"). The actor's own executions also receive faster real-time
 * updates via WebSocket (useActorExecutionSync, Story 36.2).
 * When there are no running executions, it still polls at BACKGROUND_POLL_INTERVAL_MS so new
 * executions triggered by other users eventually appear in the list.
 * Polling respects the Page Visibility API: skipped when the tab is hidden, and an immediate
 * refresh fires when the tab becomes visible again (Story 36.3).
 */
import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
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
import { useAuth } from '../contexts/AuthContext';
import { useActorExecutionSync } from './useActorExecutionSync';
import { RUNNING_STATUSES } from '../constants/executions';

const PAGE_SIZE = 25;

/** Observer polling interval: refresh the full list so status changes from other users become visible. */
const OBSERVER_POLL_INTERVAL_MS = 10_000;
/** Slower interval when no running executions, so new executions from other users appear in the list. */
const BACKGROUND_POLL_INTERVAL_MS = 30_000;

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
  // Story 36.2: trigger immediate refresh after wizard submission
  refresh: () => void;
  /** Update a single execution in the list (e.g. when drawer receives real-time completion). */
  updateExecutionInList: (id: number, patch: Partial<ExecutionResponse>) => void;
  // Computed
  PAGE_SIZE: number;
}

export const useExecutionsData = (
  filters: ExecutionFilters,
  canApprove: boolean,
): UseExecutionsDataReturn => {
  const { user } = useAuth();

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
  const refetchSilentRef = useRef<(() => Promise<void>) | null>(null);
  const hasRunningRef = useRef(false);

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

  // Silent refetch: update list + stats + time series without toggling loading (for polling).
  // In-flight guard prevents overlapping polls; list is always applied; stats/timeSeries are best-effort.
  const refetchSilent = useCallback(async () => {
    if (isRefreshingRef.current) return;
    isRefreshingRef.current = true;
    const page = currentPageRef.current;
    const scope = activeScopeRef.current;
    const offset = (page - 1) * PAGE_SIZE;
    try {
      const listResult = await listExecutions(PAGE_SIZE, offset, scope, filters);
      setExecutions(listResult.data);
      setTotalCount(listResult.pagination.total);
      // Best-effort: failures must not prevent list updates; update state only on success
      fetchExecutionStats(scope, filters)
        .then((stats) => setStatsData(stats))
        .catch(() => null);
      fetchExecutionTimeSeries(scope, filters)
        .then((data) => setTimeSeriesData(data))
        .catch(() => null);
    } catch (err) {
      logger.error('Executions poll refetch failed', { error: err instanceof Error ? err.message : String(err) });
    } finally {
      isRefreshingRef.current = false;
    }
  }, [filters]);

  // Keep hasRunningRef in sync so polling effect can read it without listing executions in deps.
  useEffect(() => {
    hasRunningRef.current = executions.some((e) => RUNNING_STATUSES.includes(e.status));
  }, [executions]);

  // Poll so the list stays up to date: observer interval when running, slower otherwise.
  // Respects Page Visibility API: skip poll when tab is hidden, fire immediately on tab focus (Story 36.3).
  // Uses refs so this effect does not re-run when executions change (avoids tearing down/restarting interval).
  useEffect(() => {
    refetchSilentRef.current = refetchSilent;

    const scheduleNext = () => {
      const delay = hasRunningRef.current ? OBSERVER_POLL_INTERVAL_MS : BACKGROUND_POLL_INTERVAL_MS;
      return window.setTimeout(() => {
        if (!document.hidden) refetchSilentRef.current?.();
        timeoutIdRef.current = scheduleNext();
      }, delay);
    };

    const timeoutIdRef = { current: scheduleNext() };

    const handleVisibility = () => {
      if (!document.hidden) refetchSilentRef.current?.();
    };
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      clearTimeout(timeoutIdRef.current);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [refetchSilent]);

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

  // Story 36.2 — Real-time WS sync for current user's active executions
  const actorActiveIds = useMemo(
    () =>
      executions
        .filter((e) => e.user_id === user?.id && ['RUNNING', 'SUBMITTED'].includes(e.status))
        .map((e) => e.id),
    [executions, user?.id],
  );

  const handleActorStatusUpdate = useCallback(
    (id: number, status: string, data?: Partial<ExecutionResponse>) => {
      setExecutions((prev) =>
        prev.map((e) => (e.id === id ? { ...e, status: status as ExecutionResponse['status'], ...(data ?? {}) } : e)),
      );
    },
    [],
  );

  useActorExecutionSync(actorActiveIds, handleActorStatusUpdate);

  // Expose refresh for post-wizard trigger (Story 36.2 AC4)
  const refresh = useCallback(() => {
    fetchData(currentPageRef.current, activeScopeRef.current);
  }, [fetchData]);

  // Update one execution in list (e.g. when detail drawer receives real-time status change)
  const updateExecutionInList = useCallback((id: number, patch: Partial<ExecutionResponse>) => {
    setExecutions((prev) =>
      prev.map((e) => (e.id === id ? { ...e, ...patch } : e)),
    );
  }, []);

  return {
    executions, loading, error, currentPage, setCurrentPage, totalCount,
    sortField, setSortField, sortOrder, setSortOrder,
    activeScope, setActiveScope, userHasChosenScope,
    statsData, statsLoading, timeSeriesData, timeSeriesLoading,
    pendingApprovals, pendingApprovalsLoading, loadPendingApprovals,
    integrationIconsMap,
    isRefreshingRef, refetchCurrentState, refresh, updateExecutionInList,
    PAGE_SIZE,
  };
};
