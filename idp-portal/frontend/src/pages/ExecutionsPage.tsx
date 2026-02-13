/**
 * ExecutionsPage - Execution history (Story 4.8, 8.8, 8.9, 9.4, 9.9, 9.10, 17.13).
 *
 * Story 17.13: Compact mode for increased density — size="small", reduced column widths,
 * compact icons (40px) and badge padding. +20% visible rows on 1080p viewport.
 *
 * AC1: Table with columns: action, environment, status, date, duration.
 * AC3: Running executions first with blue pulsed indicator.
 * AC4: Pagination 25, skeleton loading, sortable columns.
 * AC2: Click opens drawer with ExecutionTimeline (historical mode).
 *
 * Story 8.8:
 * AC1: Section "Approbations en attente" s'affiche avant la liste des exécutions.
 * AC8: Réutilisation du composant PendingApprovalsList.
 * AC9: RBAC - seuls DBA/DBOPS voient la section approbations.
 *
 * Story 8.9:
 * AC1: Tabs "Toutes les exécutions" et "Mes exécutions".
 * AC2-AC3: Tab "Toutes" shows all executions (RBAC), "Mes" shows user's executions.
 * AC4-AC5: Tab change reloads data, resets pagination, preserves sort.
 * AC6: Non-DBA/DBOPS only see "Mes exécutions" tab.
 * AC9: Column "Utilisateur" visible only for scope=all.
 *
 * Story 9.4:
 * AC1: 4 StatCards (executions du jour, taux de succès, en cours, en erreur) déplacées du Dashboard.
 * AC3: Stats reflètent le scope actif (mine/all) et filtres.
 * AC4: Responsive layout xs=24 sm=12 md=6.
 * AC5: Loading skeleton pour les cards.
 *
 * Story 9.9:
 * AC1: Colonne Statut déplacée en première position avec indicateur visuel.
 * AC2-AC3: Indicateurs pulsants (running) vs fixes (terminal).
 * AC4: Colonne Technologie avec icône engine/workflow.
 * AC5: Colonne Plateforme avec icône plateforme d'exécution (action.platform).
 * AC7: Ordre colonnes: Statut, Action, Technologie, Plateforme, [Utilisateur], Environnement, Date, Durée.
 *
 * Story 9.10:
 * AC2: TrendLineChart sous les StatCards, synchronisé avec filtres.
 * AC3: AdvancedFiltersPanel avec date range, action, technologie, tags, statut, environnement.
 * AC4: API /executions accepte filtres avancés.
 * AC5: TrendLineChart reflète les filtres appliqués.
 * AC6: StatCards reflètent les filtres appliqués.
 * AC7: Filtres persistés dans URL query params.
 * AC8: Badge nombre de filtres actifs.
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router';
import { App, Typography, Table, Drawer, Skeleton, Alert, Card, Space, Row, Col, Tag, theme, Button, Tooltip } from 'antd';
import {
  SafetyCertificateOutlined,
  RocketOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  RedoOutlined,
} from '@ant-design/icons';
import type { TableProps, TablePaginationConfig } from 'antd';
import {
  renderStatusIndicator,
  renderEngineIcon,
  renderPlateformeIcon,
} from '../utils/executionRenderers';

// Ant Design 6.2: Extract table event types from public API
type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;
type SorterResult<T> = Parameters<TableOnChange<T>>[2];
type FilterValue = Parameters<TableOnChange<never>>[1][string];
import { ExecutionTimeline } from '../components/execution/ExecutionTimeline';
import { WorkflowExecutionGraph } from '../components/execution/WorkflowExecutionGraph';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { PendingApprovalsList } from '../components/dashboard/PendingApprovalsList';
import { ExecutionsTabs } from '../components/executions/ExecutionsTabs';
import { StatCard } from '../components/dashboard/StatCard';
import { ExecutionsFiltersPanel } from '../components/executions/ExecutionsFiltersPanel';
import { TrendLineChart } from '../components/dashboard/reporting/TrendLineChart';
import { useExecutionFilters } from '../hooks/useExecutionFilters';
import {
  listExecutions,
  getExecution,
  getExecutionSteps,
  listPendingApprovals,
  fetchExecutionStats,
  fetchExecutionTimeSeries,
  cancelExecution,
} from '../services/execution_service';
import { getIntegrations } from '../services/integrations_service';
import { useAuth } from '../contexts/AuthContext';
import type { IntegrationIconsMap } from '../utils/executionRenderers';
import type {
  ExecutionResponse,
  ExecutionStepResponse,
  ExecutionStatusType,
  ExecutionScope,
  DashboardStats,
  DashboardTimeSeriesPoint,
} from '../types/api';
import type { WizardInitialParams } from '../types/wizard';
import { ExecutionWizard } from '../components/catalog/ExecutionWizard';
import { fetchCatalogActionById } from '../services/catalog_service';
import type { CatalogActionDetail } from '../services/catalog_service';
import { prepareWizardParamsFromExecution } from '../utils/executionHelpers';
import logger from '../services/logger';

const { Title } = Typography;

const PAGE_SIZE = 25;

// MEDIUM-2 fix: Extract notification messages to constants
const MESSAGES = {
  CANCEL_SUCCESS: 'Exécution annulée avec succès',
  CANCEL_ERROR_TITLE: 'Erreur d\'annulation',
  CANCEL_ERROR_FALLBACK: 'Erreur lors de l\'annulation',
  CANCEL_CONFIRM_TITLE: 'Confirmer l\'annulation',
  CANCEL_CONFIRM_CONTENT: 'Êtes-vous sûr de vouloir annuler cette exécution ? Cette action est irréversible.',
  CANCEL_CONFIRM_OK: 'Confirmer',
  CANCEL_CONFIRM_CANCEL: 'Annuler',
  RESTART_ACTION_UNAVAILABLE: 'Action non disponible — impossible de relancer cette exécution',
  RESTART_ERROR_TITLE: 'Erreur de relance',
  RESTART_ERROR_FALLBACK: 'Erreur lors de la préparation de la relance',
} as const;

/** Running statuses that appear first with visual indicator (AC3, Story 9.9 AC2). */
const RUNNING_STATUSES: ExecutionStatusType[] = ['RUNNING', 'SUBMITTED', 'PENDING_APPROVAL'];

/** Format duration from ISO timestamps. */
function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return '—';
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return remaining ? `${minutes}m ${remaining}s` : `${minutes}m`;
}

/** Format date for display. */
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Check if execution is in a running state (AC3). */
function isRunning(status: ExecutionStatusType): boolean {
  return RUNNING_STATUSES.includes(status);
}

export default function ExecutionsPage() {
  const { notification, modal } = App.useApp();
  // Story 8.8 AC9, Story 8.9: Auth context for profile check
  const { user, isLoading: authLoading } = useAuth();
  const { token } = theme.useToken();
  // Story 8.9 code-review: Consolidated RBAC logic - DBA/DBOPS can approve AND view all
  // HIGH-4 fix: Memoize RBAC checks to react to user context changes
  const canApprove = useMemo(() =>
    user?.profile?.toLowerCase() === 'dba' ||
    user?.profile?.toLowerCase() === 'dbops',
    [user?.profile]
  );
  const canViewAll = canApprove; // Same RBAC for both (Story 8.9)

  // Story 9.10: URL-synced filters
  const { filters, applyFilters, resetFilters, activeFilterCount } = useExecutionFilters();
  const params = useParams<{ id?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Integration icons for Plateforme column fallback (icons set in integration page)
  const [integrationIconsMap, setIntegrationIconsMap] = useState<IntegrationIconsMap | null>(null);

  const [executions, setExecutions] = useState<ExecutionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [sortField, setSortField] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend');

  // Story 8.9: Scope state for tabs — default "Toutes les exécutions" for DBA/DBOPS
  const [activeScope, setActiveScope] = useState<ExecutionScope>('all');
  const userHasChosenScope = useRef(false);

  // Scope sync: mine while auth loads; all for DBA/DBOPS when ready; mine for others (only before user interaction)
  useEffect(() => {
    if (userHasChosenScope.current) return;
    if (authLoading) {
      if (activeScope !== 'mine') setActiveScope('mine');
      return;
    }
    if (canViewAll && activeScope === 'mine') {
      setActiveScope('all');
      return;
    }
    if (!canViewAll && activeScope === 'all') {
      setActiveScope('mine');
    }
  }, [authLoading, canViewAll, activeScope]);

  // Story 9.10: Time series data for TrendLineChart
  const [timeSeriesData, setTimeSeriesData] = useState<DashboardTimeSeriesPoint[]>([]);
  const [timeSeriesLoading, setTimeSeriesLoading] = useState(true);

  // Story 8.8 AC1, AC2: Pending approvals section
  const [pendingApprovals, setPendingApprovals] = useState<ExecutionResponse[]>([]);
  const [pendingApprovalsLoading, setPendingApprovalsLoading] = useState(false);

  // Drawer state (AC2)
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResponse | null>(null);
  const [selectedSteps, setSelectedSteps] = useState<ExecutionStepResponse[]>([]);
  const [selectedActionDetail, setSelectedActionDetail] = useState<CatalogActionDetail | null>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  // Story 9.4: Execution statistics state (AC1, AC3)
  const [statsData, setStatsData] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Fetch executions (AC4: pagination with total from API; Story 8.9: scope filter; Story 9.10: filters)
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

  useEffect(() => {
    fetchData(currentPage, activeScope);
  }, [currentPage, activeScope, fetchData]);

  // Open drawer from URL: /executions/:id or /executions?open=79
  const openExecutionId = params.id || searchParams.get('open');
  useEffect(() => {
    if (!openExecutionId) return;
    const id = parseInt(openExecutionId, 10);
    if (isNaN(id)) return;

    const doOpen = async () => {
      setDrawerOpen(true);
      setDrawerLoading(true);
      setDrawerError(null);
      setSelectedExecution(null);
      setSelectedSteps([]);
      setSelectedActionDetail(null);
      try {
        const [execution, steps] = await Promise.all([
          getExecution(id),
          getExecutionSteps(id),
        ]);
        setSelectedExecution(execution);
        setSelectedSteps(steps);
        if (execution.item_type === 'workflow' && execution.action_id) {
          try {
            const { data } = await fetchCatalogActionById(execution.action_id);
            setSelectedActionDetail(data);
          } catch {
            // Fallback: show timeline if action detail fails
          }
        }
      } catch (err) {
        setDrawerError(err instanceof Error ? err.message : 'Erreur de chargement du détail');
      } finally {
        setDrawerLoading(false);
      }
    }

    doOpen();
  }, [openExecutionId]);

  // Reset to page 1 when filters change (apply-on-change UX)
  useEffect(() => {
    setCurrentPage(1);
  }, [filters]);

  // Story 9.10 AC5: Fetch time series data for TrendLineChart
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

  // Story 8.9 AC4, AC5: Handle scope change - reset pagination, preserve sort
  const handleScopeChange = useCallback((scope: ExecutionScope) => {
    userHasChosenScope.current = true;
    setActiveScope(scope);
    setCurrentPage(1); // Reset pagination (AC4)
    // Sort is preserved (AC5) - sortField and sortOrder remain unchanged
  }, []);

  // Story 8.8 AC1: Load pending approvals for DBA/DBOPS
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

  useEffect(() => {
    loadPendingApprovals();
  }, [loadPendingApprovals]);

  // Load integrations for Plateforme column icons (fallback when execution has no integration_icon)
  useEffect(() => {
    let cancelled = false;
    getIntegrations()
      .then((list) => {
        if (cancelled) return;
        const map: IntegrationIconsMap = {};
        const typeToPlatform: Record<string, string> = {
          aap: 'AAP',
          terraform: 'Terraform',
          azuredevops: 'Azure DevOps',
          github_actions: 'GitHub Actions',
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
      .catch(() => {
        if (!cancelled) setIntegrationIconsMap(null);
      });
    return () => { cancelled = true; };
  }, []);

  // Story 9.4 AC3, Story 9.10 AC6: Load stats when scope or filters change
  useEffect(() => {
    async function loadStats() {
      setStatsLoading(true);
      try {
        const stats = await fetchExecutionStats(activeScope, filters);
        setStatsData(stats);
      } catch (err) {
        logger.error('Erreur chargement stats', { error: err instanceof Error ? err.message : String(err) });
        // Afficher stats vides plutôt que bloquer l'UI
        setStatsData({
          executions_jour: 0,
          taux_succes_pct: 0,
          executions_en_cours: 0,
          executions_en_erreur: 0,
        });
      } finally {
        setStatsLoading(false);
      }
    }

    loadStats();
  }, [activeScope, filters]);

  /**
   * Refs to track current page and scope at call time (not closure creation time).
   * Solves stale closure issue (Story 22.14 / HIGH-7): callbacks created before a
   * pagination or scope change would otherwise capture outdated values.
   */
  const currentPageRef = useRef(currentPage);
  const activeScopeRef = useRef(activeScope);

  useEffect(() => {
    currentPageRef.current = currentPage;
  }, [currentPage]);

  useEffect(() => {
    activeScopeRef.current = activeScope;
  }, [activeScope]);

  /**
   * Refetch using the current page and scope at call time (not closure creation time).
   *
   * **Problem Solved (Story 22.14 / HIGH-7):**
   * React callbacks capture values in their closure at creation time. If a user:
   * 1. Clicks "Cancel" (creates callback with page=1, scope="all")
   * 2. Changes to page=2, scope="mine" BEFORE confirming the modal
   * 3. Confirms cancel → the callback would call fetchData(1, "all") [WRONG!]
   *
   * **Solution:**
   * This function reads from refs which are updated synchronously, so it ALWAYS
   * uses the latest values regardless of when the enclosing callback was created.
   *
   * @see currentPageRef, activeScopeRef - synchronized with state via useEffect
   * @see handleCancelExecution, handleApprovalComplete, handleRestartSuccess - usage
   */
  const refetchCurrentState = useCallback(() => {
    return fetchData(currentPageRef.current, activeScopeRef.current);
  }, [fetchData]);

  // Story 22.14: Guards to prevent concurrent cancel/refresh operations
  const isCancellingRef = useRef(false);
  const isRefreshingRef = useRef(false);

  // Story 17.14: Cancel execution state
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  // Story 17.15: Restart execution state
  const [restartWizardOpen, setRestartWizardOpen] = useState(false);
  const [restartAction, setRestartAction] = useState<CatalogActionDetail | null>(null);
  const [restartAllowedEnvs, setRestartAllowedEnvs] = useState<string[]>([]);
  const [restartInitialParams, setRestartInitialParams] = useState<WizardInitialParams | undefined>(undefined);
  const [restartLoadingId, setRestartLoadingId] = useState<number | null>(null);

  // Story 17.14 AC3: Handle cancel execution with confirmation modal
  // Story 22.14: Uses refetchCurrentState (refs) to avoid stale closure + isCancellingRef guard
  const handleCancelExecution = useCallback((executionId: number) => {
    // Guard: block if cancel already in progress OR if this execution is already being cancelled
    if (isCancellingRef.current || cancellingId === executionId) {
      logger.debug('Cancel operation already in progress or modal open, ignoring duplicate', {
        executionId,
        correlation_id: crypto.randomUUID(),
      });
      return;
    }

    modal.confirm({
      title: MESSAGES.CANCEL_CONFIRM_TITLE,
      content: MESSAGES.CANCEL_CONFIRM_CONTENT,
      okText: MESSAGES.CANCEL_CONFIRM_OK,
      cancelText: MESSAGES.CANCEL_CONFIRM_CANCEL,
      okButtonProps: { danger: true },
      onOk: async () => {
        isCancellingRef.current = true;
        setCancellingId(executionId);
        try {
          await cancelExecution(executionId);
          notification.success({ message: MESSAGES.CANCEL_SUCCESS });
          if (!isRefreshingRef.current) {
            isRefreshingRef.current = true;
            try {
              await refetchCurrentState();
            } finally {
              isRefreshingRef.current = false;
            }
          }
        } catch (err) {
          const message = err instanceof Error ? err.message : MESSAGES.CANCEL_ERROR_FALLBACK;
          notification.error({ message: MESSAGES.CANCEL_ERROR_TITLE, description: message });
          logger.error('Cancel execution failed', { executionId, error: message });
        } finally {
          isCancellingRef.current = false;
          setCancellingId(null);
        }
      },
    });
  }, [modal, notification, refetchCurrentState, cancellingId]);

  // Story 17.15 AC1, AC2: Handle restart execution — load action and open wizard
  const handleRestartExecution = useCallback(async (execution: ExecutionResponse) => {
    logger.debug('Restart execution requested', { executionId: execution.id, actionId: execution.action_id });

    // AC6: Check if action exists
    if (!execution.action_id) {
      notification.error({ message: MESSAGES.RESTART_ERROR_TITLE, description: MESSAGES.RESTART_ACTION_UNAVAILABLE });
      logger.error('Restart failed: no action_id', { executionId: execution.id });
      return;
    }

    setRestartLoadingId(execution.id);
    try {
      const response = await fetchCatalogActionById(execution.action_id);
      const wizardParams = prepareWizardParamsFromExecution(execution);

      if (!wizardParams) {
        notification.error({ message: MESSAGES.RESTART_ERROR_TITLE, description: MESSAGES.RESTART_ACTION_UNAVAILABLE });
        logger.error('Restart failed: could not prepare params', { executionId: execution.id });
        return;
      }

      setRestartAction(response.data);
      setRestartAllowedEnvs(response.allowed_environments);
      setRestartInitialParams(wizardParams);
      setRestartWizardOpen(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : MESSAGES.RESTART_ERROR_FALLBACK;
      notification.error({ message: MESSAGES.RESTART_ERROR_TITLE, description: message });
      logger.error('Restart execution failed', { executionId: execution.id, error: message });
    } finally {
      setRestartLoadingId(null);
    }
  }, [notification]);

  // Story 17.15: Close restart wizard and refresh
  const handleRestartWizardClose = useCallback(() => {
    setRestartWizardOpen(false);
    setRestartAction(null);
    setRestartAllowedEnvs([]);
    setRestartInitialParams(undefined);
  }, []);

  // Story 22.14: Uses refetchCurrentState (refs) to avoid stale closure + isRefreshingRef guard
  const handleRestartSuccess = useCallback((executionId: number) => {
    handleRestartWizardClose();

    if (!isRefreshingRef.current) {
      isRefreshingRef.current = true;
      refetchCurrentState().finally(() => {
        isRefreshingRef.current = false;
      });
    }

    logger.debug('Restart execution created', { executionId });
  }, [handleRestartWizardClose, refetchCurrentState]);

  // Story 8.8: Callback after approval/rejection - refresh both lists
  // Story 22.14: Uses refetchCurrentState (refs) to avoid stale closure + isRefreshingRef guard
  const handleApprovalComplete = useCallback(() => {
    loadPendingApprovals();
    if (!isRefreshingRef.current) {
      isRefreshingRef.current = true;
      refetchCurrentState().finally(() => {
        isRefreshingRef.current = false;
      });
    }
  }, [loadPendingApprovals, refetchCurrentState]);

  // Group workflow children under parent (accordion-style)
  const { topLevelExecutions, childrenByParentId } = useMemo(() => {
    const childrenMap = new Map<number, ExecutionResponse[]>();
    for (const e of executions) {
      if (e.parent_execution_id != null) {
        const list = childrenMap.get(e.parent_execution_id) ?? [];
        list.push(e);
        childrenMap.set(e.parent_execution_id, list);
      }
    }
    // Sort children by created_at
    for (const list of childrenMap.values()) {
      list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    }
    const topLevel = executions.filter((e) => e.parent_execution_id == null);
    return { topLevelExecutions: topLevel, childrenByParentId: childrenMap };
  }, [executions]);

  // Sort top-level executions: running first, then by sortField (AC3)
  const sortedExecutions = useMemo(() => {
    const sorted = [...topLevelExecutions];

    sorted.sort((a, b) => {
      const aRunning = isRunning(a.status) ? 0 : 1;
      const bRunning = isRunning(b.status) ? 0 : 1;
      if (aRunning !== bRunning) return aRunning - bRunning;

      let aVal: string | number | null = null;
      let bVal: string | number | null = null;

      if (sortField === 'created_at') {
        aVal = a.created_at;
        bVal = b.created_at;
      } else if (sortField === 'status') {
        aVal = a.status;
        bVal = b.status;
      } else if (sortField === 'action_name') {
        aVal = a.action_name || '';
        bVal = b.action_name || '';
      }

      if (aVal === null || bVal === null) return 0;
      if (aVal < bVal) return sortOrder === 'ascend' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'ascend' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [topLevelExecutions, sortField, sortOrder]);

  // Open drawer with execution details (AC2)
  const handleRowClick = async (record: ExecutionResponse) => {
    setDrawerOpen(true);
    setDrawerLoading(true);
    setDrawerError(null);
    setSelectedExecution(null);
    setSelectedSteps([]);
    setSelectedActionDetail(null);

    try {
      const [execution, steps] = await Promise.all([
        getExecution(record.id),
        getExecutionSteps(record.id),
      ]);
      setSelectedExecution(execution);
      setSelectedSteps(steps);
      if (execution.item_type === 'workflow' && execution.action_id) {
        try {
          const { data } = await fetchCatalogActionById(execution.action_id);
          setSelectedActionDetail(data);
        } catch {
          // Fallback: show timeline if action detail fails
        }
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erreur de chargement du détail';
      setDrawerError(message);
    } finally {
      setDrawerLoading(false);
    }
  };

  const handleTableChange = (
    pagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>,
    sorter: SorterResult<ExecutionResponse> | SorterResult<ExecutionResponse>[],
  ) => {
    if (pagination.current && pagination.current !== currentPage) {
      setCurrentPage(pagination.current);
    }

    const singleSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    if (singleSorter?.field) {
      setSortField(singleSorter.field as string);
      setSortOrder(singleSorter.order || 'descend');
    }
  };

  // Table columns (Story 9.9 AC7: Statut, Action, Technologie, Plateforme, [Utilisateur], Environnement, Date, Durée)
  const columns: TableProps<ExecutionResponse>['columns'] = useMemo(() => {
    const baseColumns: TableProps<ExecutionResponse>['columns'] = [
      // Story 9.9 AC1: Colonne Statut en première position
      {
        title: 'Statut',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        align: 'center' as const,
        render: (status: ExecutionStatusType) => renderStatusIndicator(status),
        sorter: false, // Story 9.9 AC7: Statut not sortable
      },
      // Story 9.9 AC7: Colonne Action (sans badge inline)
      {
        title: 'Action',
        dataIndex: 'action_name',
        key: 'action_name',
        sorter: true,
        sortOrder: sortField === 'action_name' ? sortOrder : undefined,
        render: (name: string | null, record: ExecutionResponse) =>
          name || `Action #${record.action_id}`,
      },
      // Story 9.9 AC4: Colonne Technologie avec icône engine/workflow
      {
        title: 'Technologie',
        key: 'engine',
        width: 100,
        align: 'center' as const,
        render: (_: unknown, record: ExecutionResponse) =>
          renderEngineIcon(record.engine, record.item_type),
        sorter: false, // Story 9.9 AC7: Technologie not sortable
      },
      // Story 9.9 AC5: Colonne Plateforme = icône intégration si définie, sinon plateforme d'exécution
      {
        title: 'Plateforme',
        key: 'integration',
        width: 100,
        align: 'center' as const,
        render: (_: unknown, record: ExecutionResponse) =>
          renderPlateformeIcon(
            record.integration_name,
            record.integration_icon,
            record.platform,
            integrationIconsMap,
          ),
        sorter: false, // Story 9.9 AC7: Plateforme not sortable
      },
    ];

    // Story 8.9 AC9: Add "Utilisateur" column only for scope=all
    if (activeScope === 'all') {
      baseColumns.push({
        title: 'Utilisateur',
        dataIndex: 'user_display_name',
        key: 'user_display_name',
        width: 130,
        render: (name: string | null) => name || 'Utilisateur inconnu',
      });
    }

    baseColumns.push(
      {
        title: 'Environnement',
        dataIndex: 'environment',
        key: 'environment',
        width: 120,
        render: (env: string) => env?.toUpperCase() || '—',
      },
      {
        title: 'Date',
        dataIndex: 'created_at',
        key: 'created_at',
        sorter: true,
        sortOrder: sortField === 'created_at' ? sortOrder : undefined,
        width: 160,
        render: (date: string, record: ExecutionResponse) => formatDate(record.started_at || date),
      },
      {
        title: 'Durée',
        key: 'duration',
        width: 80,
        render: (_: unknown, record: ExecutionResponse) =>
          formatDuration(record.started_at, record.completed_at),
      },
      // Story 17.14 AC1, AC2; Story 17.15 AC1, AC2: Colonne Actions avec boutons Annuler et Relancer
      {
        title: 'Actions',
        key: 'actions',
        width: 100,
        align: 'center' as const,
        render: (_: unknown, record: ExecutionResponse) => {
          const isCancellable = record.status === 'SUBMITTED' || record.status === 'RUNNING';
          const canCancel = isCancellable && (
            record.user_id === user?.id || canViewAll
          );
          // Story 17.15 AC1, AC2: Restart visible for initiator OR admin (DBA/DBOPS)
          const canRestart = record.user_id === user?.id || canViewAll;

          if (!canCancel && !canRestart) return null;
          return (
            <Space size={4}>
              {canRestart && (
                <Tooltip title="Relancer l'exécution avec les mêmes paramètres">
                  <Button
                    type="default"
                    size="small"
                    icon={<RedoOutlined />}
                    aria-label="Relancer"
                    loading={restartLoadingId === record.id}
                    onClick={(e) => { e.stopPropagation(); handleRestartExecution(record); }}
                  />
                </Tooltip>
              )}
              {canCancel && (
                <Tooltip title="Annuler l'exécution">
                  <Button
                    type="text"
                    danger
                    size="small"
                    icon={<CloseCircleOutlined />}
                    aria-label="Annuler"
                    loading={cancellingId === record.id}
                    onClick={(e) => { e.stopPropagation(); handleCancelExecution(record.id); }}
                  />
                </Tooltip>
              )}
            </Space>
          );
        },
      },
    );

    return baseColumns;
  }, [activeScope, sortField, sortOrder, integrationIconsMap, user, canViewAll, cancellingId, handleCancelExecution, restartLoadingId, handleRestartExecution]);

  // Skeleton table during loading (AC4, Task 1.4: skeleton rows; Story 9.9: updated column order)
  if (loading && executions.length === 0) {
    const skeletonColumns = [
      { title: 'Statut', key: 'status', width: 120, render: () => <Skeleton.Button active size="small" /> },
      { title: 'Action', key: 'action', width: 200, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Technologie', key: 'engine', width: 100, render: () => <Skeleton.Button active size="small" /> },
      { title: 'Plateforme', key: 'integration', width: 120, render: () => <Skeleton.Button active size="small" /> },
      // Story 9.9 code-review fix: Add Utilisateur column if scope=all
      ...(activeScope === 'all' ? [
        { title: 'Utilisateur', key: 'user', width: 150, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      ] : []),
      { title: 'Environnement', key: 'env', width: 120, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Date', key: 'date', width: 160, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Durée', key: 'duration', width: 100, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
    ];
    const skeletonData = Array.from({ length: 10 }, (_, i) => ({ key: i }));
    return (
      <div style={{ padding: 24 }}>
        <Title level={2}>Exécutions</Title>
        <Table
          columns={skeletonColumns}
          dataSource={skeletonData}
          rowKey="key"
          size="small"
          pagination={false}
          showHeader
        />
      </div>
    );
  }

  if (error && executions.length === 0) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={2}>Exécutions</Title>
        <Typography.Text type="danger">{error}</Typography.Text>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Exécutions</Title>

      {/* Story 9.4 AC1, AC3, AC4, AC5; Story 9.10 AC6: StatCards section (filter-aware) */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label={filters.start_date || filters.end_date ? "Exécutions" : "Exécutions du jour"}
            value={statsData?.executions_jour ?? 0}
            icon={<RocketOutlined />}
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="Taux de succès"
            value={statsData?.taux_succes_pct ?? 0}
            suffix="%"
            icon={<CheckCircleOutlined />}
            variant="success"
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En cours"
            value={statsData?.executions_en_cours ?? 0}
            icon={<SyncOutlined spin={!statsLoading && (statsData?.executions_en_cours ?? 0) > 0} />}
            variant="inProgress"
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En erreur"
            value={statsData?.executions_en_erreur ?? 0}
            icon={<ExclamationCircleOutlined />}
            variant="error"
            loading={statsLoading}
          />
        </Col>
      </Row>

      {/* Story 9.10 AC2, AC5: TrendLineChart (filter-aware) */}
      <div style={{ marginBottom: 16 }}>
        <TrendLineChart data={timeSeriesData} loading={timeSeriesLoading} />
      </div>

      {/* Story 9.10 AC3, AC8: Advanced filters panel */}
      <ExecutionsFiltersPanel
        filters={filters}
        onApplyFilters={applyFilters}
        onResetFilters={resetFilters}
        activeFilterCount={activeFilterCount}
        loading={loading}
      />

      {/* Story 8.8 AC1, AC8: Pending approvals section (DBA/DBOPS only) */}
      {canApprove && pendingApprovals.length > 0 && (
        <Card
          id="pending-approvals"
          title={
            <Space>
              <SafetyCertificateOutlined style={{ color: token.colorWarning }} />
              <span>Approbations en attente</span>
              <Tag color="warning">{pendingApprovals.length}</Tag>
            </Space>
          }
          style={{ marginBottom: 24, borderColor: token.colorWarning }}
        >
          <PendingApprovalsList
            executions={pendingApprovals}
            loading={pendingApprovalsLoading}
            onActionComplete={handleApprovalComplete}
          />
        </Card>
      )}

      {/* Story 8.9: Tabs for execution scope (Toutes/Mes exécutions) */}
      <ExecutionsTabs
        activeScope={activeScope}
        onScopeChange={handleScopeChange}
        canViewAll={canViewAll}
      />

      <Table<ExecutionResponse>
        dataSource={sortedExecutions}
        columns={columns}
        rowKey="id"
        size="small"
        loading={loading}
        pagination={{
          current: currentPage,
          pageSize: PAGE_SIZE,
          total: totalCount,
          showSizeChanger: false,
        }}
        onChange={handleTableChange}
        onRow={(record) => ({
          onClick: () => handleRowClick(record),
          style: { cursor: 'pointer' },
        })}
        expandable={{
          rowExpandable: (record) =>
            record.item_type === 'workflow' &&
            (childrenByParentId.get(record.id)?.length ?? 0) > 0,
          expandedRowRender: (record) => {
            const children = childrenByParentId.get(record.id) ?? [];
            if (children.length === 0) return null;
            return (
              <div style={{ padding: '8px 0 8px 24px', background: token.colorFillQuaternary }}>
                <Typography.Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                  Actions du workflow ({children.length})
                </Typography.Text>
                <Table<ExecutionResponse>
                  dataSource={children}
                  rowKey="id"
                  size="small"
                  pagination={false}
                  showHeader
                  onRow={(childRecord) => ({
                    onClick: (e) => { e.stopPropagation(); handleRowClick(childRecord); },
                    style: { cursor: 'pointer' },
                  })}
                  columns={columns}
                />
              </div>
            );
          },
        }}
        locale={{
          emptyText: 'Aucune exécution trouvée',
        }}
      />

      {/* Drawer with ExecutionTimeline (AC2) */}
      <Drawer
        title={selectedExecution ? `Exécution — ${selectedExecution.action_name || `Action #${selectedExecution.action_id}`}` : 'Détail exécution'}
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setDrawerError(null);
          if (params.id) {
            navigate('/executions', { replace: true });
          } else if (searchParams.has('open')) {
            searchParams.delete('open');
            setSearchParams(searchParams, { replace: true });
          }
        }}
        width={selectedExecution?.item_type === 'workflow' && selectedActionDetail?.workflow_steps ? 'min(90vw, 1400px)' : 480}
        destroyOnHidden
      >
        {drawerLoading ? (
          <Skeleton active paragraph={{ rows: 6 }} />
        ) : drawerError ? (
          <Alert type="error" title="Erreur de chargement" description={drawerError} showIcon />
        ) : selectedExecution ? (
          selectedExecution.item_type === 'workflow' &&
          selectedActionDetail?.workflow_steps &&
          selectedActionDetail.workflow_steps.length > 0 ? (
            <ErrorBoundary
              fallback={(error, resetError) => (
                <div style={{ padding: 16 }}>
                  <Alert type="error" showIcon message="Erreur d'affichage du workflow" description={error.message} />
                  <Button onClick={resetError} style={{ marginTop: 8 }}>Réessayer</Button>
                </div>
              )}
            >
              <WorkflowExecutionGraph
                executionId={selectedExecution.id}
                workflowSteps={selectedActionDetail.workflow_steps}
                execution={selectedExecution}
                onExecutionUpdate={(updated) => setSelectedExecution((prev) => prev ? { ...prev, status: updated.status, completed_at: updated.completed_at, started_at: updated.started_at ?? prev.started_at } : prev)}
              />
            </ErrorBoundary>
          ) : (
            <ExecutionTimeline
              execution={selectedExecution}
              steps={selectedSteps}
              mode="historical"
            />
          )
        ) : null}
      </Drawer>

      {/* Story 17.15: Restart execution wizard */}
      <ExecutionWizard
        open={restartWizardOpen}
        action={restartAction}
        allowedEnvironments={restartAllowedEnvs}
        onCancel={handleRestartWizardClose}
        onSuccess={handleRestartSuccess}
        initialParams={restartInitialParams}
      />
    </div>
  );
}
