/**
 * useAuditFilters Hook — Story 34.11 (SOLID-FE-3)
 *
 * Extracted from AuditPage.tsx. Manages all audit UI state:
 * filters, data loading, pagination, sort, drawer, export.
 *
 * Pattern: same as useCatalogState (Story 34-10), useCalendarState (Story 26.6).
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { App } from 'antd';
import type { Dayjs } from 'dayjs';
import type { TableProps } from 'antd';
import { listExecutionAudit, exportAuditReport } from '../services/audit_service';
import { fetchCatalogActions, type CatalogAction } from '../services/catalog_service';
import { getExecution, getExecutionSteps } from '../services/execution_service';
import { useEngines } from './useEngines';
import type {
  AuditExecutionEntry,
  AuditStatusFilter,
  ExecutionResponse,
  ExecutionStepResponse,
  PaginationInfo,
} from '../types/api';

type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;

const DEFAULT_PAGE_SIZE = 50;

export interface UseAuditFiltersReturn {
  // Table data
  entries: AuditExecutionEntry[];
  pagination: PaginationInfo | null;
  loading: boolean;
  error: string | null;
  topLevelEntries: AuditExecutionEntry[];
  childrenByParentId: Map<number, AuditExecutionEntry[]>;
  // Filtres
  dateRange: [Dayjs | null, Dayjs | null];
  setDateRange: React.Dispatch<React.SetStateAction<[Dayjs | null, Dayjs | null]>>;
  environment: string | undefined;
  setEnvironment: React.Dispatch<React.SetStateAction<string | undefined>>;
  engineType: string | undefined;
  setEngineType: React.Dispatch<React.SetStateAction<string | undefined>>;
  actionId: number | undefined;
  setActionId: React.Dispatch<React.SetStateAction<number | undefined>>;
  status: AuditStatusFilter | undefined;
  setStatus: React.Dispatch<React.SetStateAction<AuditStatusFilter | undefined>>;
  correlationId: string;
  setCorrelationId: React.Dispatch<React.SetStateAction<string>>;
  // Pagination / tri
  currentPage: number;
  pageSize: number;
  sortField: string;
  sortOrder: 'ascend' | 'descend';
  // Données auxiliaires
  actions: CatalogAction[];
  actionsLoading: boolean;
  engineOptions: { value: string; label: string }[];
  enginesLoading: boolean;
  // Drawer
  drawerOpen: boolean;
  selectedEntry: AuditExecutionEntry | null;
  selectedExecution: ExecutionResponse | null;
  selectedSteps: ExecutionStepResponse[];
  drawerLoading: boolean;
  drawerError: string | null;
  handleRowClick: (record: AuditExecutionEntry) => Promise<void>;
  handleDrawerClose: () => void;
  // Table
  handleTableChange: TableOnChange<AuditExecutionEntry>;
  // Export
  exporting: boolean;
  handleExport: (format: 'csv' | 'pdf') => Promise<void>;
}

export function useAuditFilters(): UseAuditFiltersReturn {
  const { message } = App.useApp();
  const { engineOptions, loading: enginesLoading } = useEngines();

  // Table data
  const [entries, setEntries] = useState<AuditExecutionEntry[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters (AC2)
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null]>([null, null]);
  const [environment, setEnvironment] = useState<string | undefined>();
  const [engineType, setEngineType] = useState<string | undefined>();
  const [actionId, setActionId] = useState<number | undefined>();
  const [status, setStatus] = useState<AuditStatusFilter | undefined>();
  const [correlationId, setCorrelationId] = useState<string>('');
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [sortField, setSortField] = useState<string>('timestamp');
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend');

  // Actions list for filter dropdown
  const [actions, setActions] = useState<CatalogAction[]>([]);
  const [actionsLoading, setActionsLoading] = useState(false);

  // Drawer state (AC3)
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<AuditExecutionEntry | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResponse | null>(null);
  const [selectedSteps, setSelectedSteps] = useState<ExecutionStepResponse[]>([]);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  // Export
  const [exporting, setExporting] = useState(false);

  // Fetch data (AC2, AC5)
  const fetchData = useCallback(async (page: number) => {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * pageSize;
      // Map frontend sort field names to API sort field names
      const apiSortField = sortField === 'action' ? 'action_type' : sortField;
      const apiSortOrder = sortOrder === 'ascend' ? 'asc' : 'desc';

      const result = await listExecutionAudit({
        from: dateRange[0]?.startOf('day').toISOString(),
        to: dateRange[1]?.endOf('day').toISOString(),
        environment,
        engine_type: engineType,
        action_id: actionId,
        status,
        correlation_id: correlationId || undefined,
        sort: apiSortField,
        order: apiSortOrder,
        limit: pageSize,
        offset,
      });
      setEntries(result.data);
      setPagination(result.pagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [dateRange, environment, engineType, actionId, status, correlationId, sortField, sortOrder, pageSize]);

  // Initial load and filter changes
  useEffect(() => {
    fetchData(currentPage);
  }, [fetchData, currentPage]);

  // Reset to page 1 when filters, sort or page size change
  useEffect(() => {
    setCurrentPage(1);
  }, [dateRange, environment, engineType, actionId, status, correlationId, sortField, sortOrder, pageSize]);

  // Load published actions for filter dropdown
  useEffect(() => {
    let cancelled = false;
    setActionsLoading(true);
    fetchCatalogActions()
      .then((data) => {
        if (!cancelled) setActions(data);
      })
      .catch(() => {
        if (!cancelled) setActions([]);
      })
      .finally(() => {
        if (!cancelled) setActionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Open drawer with details (AC3)
  const handleRowClick = useCallback(async (record: AuditExecutionEntry) => {
    setDrawerOpen(true);
    setDrawerLoading(true);
    setDrawerError(null);
    setSelectedEntry(record);
    setSelectedExecution(null);
    setSelectedSteps([]);

    try {
      if (record.entity_id) {
        const [execution, steps] = await Promise.all([
          getExecution(record.entity_id),
          getExecutionSteps(record.entity_id),
        ]);
        setSelectedExecution(execution);
        setSelectedSteps(steps);
      }
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Erreur de chargement du détail';
      setDrawerError(errMsg);
    } finally {
      setDrawerLoading(false);
    }
  }, []);

  const handleDrawerClose = useCallback(() => {
    setDrawerOpen(false);
    setDrawerError(null);
  }, []);

  // Table change handler (AC4, AC5)
  const handleTableChange = useCallback<TableOnChange<AuditExecutionEntry>>(
    (paginationConfig, _filters, sorter) => {
      if (paginationConfig.current && paginationConfig.current !== currentPage) {
        setCurrentPage(paginationConfig.current);
      }
      if (paginationConfig.pageSize && paginationConfig.pageSize !== pageSize) {
        setPageSize(paginationConfig.pageSize);
        setCurrentPage(1);
      }

      const singleSorter = Array.isArray(sorter) ? sorter[0] : sorter;
      if (singleSorter?.field) {
        if (singleSorter.order) {
          setSortField(singleSorter.field as string);
          setSortOrder(singleSorter.order);
        } else {
          // User removed sort — reset to default
          setSortField('timestamp');
          setSortOrder('descend');
        }
      }
    },
    [currentPage, pageSize],
  );

  // Export handler (Story 6.4, AC1, AC2, AC3, AC5)
  const handleExport = useCallback(async (format: 'csv' | 'pdf') => {
    setExporting(true);
    try {
      const apiSortField = sortField === 'action' ? 'action_type' : sortField;
      const apiSortOrder = sortOrder === 'ascend' ? 'asc' : 'desc';
      await exportAuditReport(format, {
        from: dateRange[0]?.startOf('day').toISOString(),
        to: dateRange[1]?.endOf('day').toISOString(),
        environment,
        engine_type: engineType,
        action_id: actionId,
        status,
        correlation_id: correlationId || undefined,
        sort: apiSortField,
        order: apiSortOrder,
      });
      message.success('Rapport exporté — Télécharger', 3);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Erreur lors de l'export";
      message.error(errorMessage, 5);
    } finally {
      setExporting(false);
    }
  }, [dateRange, environment, engineType, actionId, status, correlationId, sortField, sortOrder, message]);

  // Group workflow children under parent (accordion-style)
  const { topLevelEntries, childrenByParentId } = useMemo(() => {
    const childrenMap = new Map<number, AuditExecutionEntry[]>();
    for (const e of entries) {
      if (e.parent_execution_id != null) {
        const existing = childrenMap.get(e.parent_execution_id) ?? [];
        existing.push(e);
        childrenMap.set(e.parent_execution_id, existing);
      }
    }
    const topLevel = entries.filter((e) => e.parent_execution_id == null);
    return { topLevelEntries: topLevel, childrenByParentId: childrenMap };
  }, [entries]);

  return {
    entries,
    pagination,
    loading,
    error,
    topLevelEntries,
    childrenByParentId,
    dateRange,
    setDateRange,
    environment,
    setEnvironment,
    engineType,
    setEngineType,
    actionId,
    setActionId,
    status,
    setStatus,
    correlationId,
    setCorrelationId,
    currentPage,
    pageSize,
    sortField,
    sortOrder,
    actions,
    actionsLoading,
    engineOptions,
    enginesLoading,
    drawerOpen,
    selectedEntry,
    selectedExecution,
    selectedSteps,
    drawerLoading,
    drawerError,
    handleRowClick,
    handleDrawerClose,
    handleTableChange,
    exporting,
    handleExport,
  };
}
