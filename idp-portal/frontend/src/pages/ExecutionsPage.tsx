/**
 * ExecutionsPage - Execution history (Story 4.8, 8.8, 8.9, 9.4, 9.9, 9.10, 17.13).
 *
 * Story 26.4: Refactored from 1023 LOC monolith to orchestrator pattern.
 * Columns → executionsColumns.tsx, Drawer → useExecutionDetail + ExecutionDetailDrawer,
 * Restart → useExecutionRestart, Stats → ExecutionsStatSection, Data → useExecutionsData.
 */

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { App, Typography, Table, Skeleton, Card, Space, Tag, theme } from 'antd';
import { SafetyCertificateOutlined } from '@ant-design/icons';
import type { TableProps, TablePaginationConfig } from 'antd';

type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;
type SorterResult<T> = Parameters<TableOnChange<T>>[2];
type FilterValue = Parameters<TableOnChange<never>>[1][string];

import { PendingApprovalsList } from '../components/dashboard/PendingApprovalsList';
import { ExecutionsTabs } from '../components/executions/ExecutionsTabs';
import { ExecutionsFiltersPanel } from '../components/executions/ExecutionsFiltersPanel';
import { ExecutionsStatSection } from '../components/executions/ExecutionsStatSection';
import { ExecutionDetailDrawer } from '../components/executions/ExecutionDetailDrawer';
import { useExecutionFilters } from '../hooks/useExecutionFilters';
import { useExecutionDetail } from '../hooks/useExecutionDetail';
import { useExecutionRestart } from '../hooks/useExecutionRestart';
import { useExecutionsData } from '../hooks/useExecutionsData';
import { getExecutionsColumns, isRunning } from './executions/executionsColumns';
import { cancelExecution } from '../services/execution_service';
import { useAuth } from '../contexts/AuthContext';
import type { ExecutionResponse } from '../types/api';
import { ExecutionWizard } from '../components/catalog/ExecutionWizard';
import logger from '../services/logger';

const { Title } = Typography;

const MESSAGES = {
  CANCEL_SUCCESS: 'Exécution annulée avec succès',
  CANCEL_ERROR_TITLE: 'Erreur d\'annulation',
  CANCEL_ERROR_FALLBACK: 'Erreur lors de l\'annulation',
  CANCEL_CONFIRM_TITLE: 'Confirmer l\'annulation',
  CANCEL_CONFIRM_CONTENT: 'Êtes-vous sûr de vouloir annuler cette exécution ? Cette action est irréversible.',
  CANCEL_CONFIRM_OK: 'Confirmer',
  CANCEL_CONFIRM_CANCEL: 'Annuler',
} as const;

export default function ExecutionsPage() {
  const { notification, modal } = App.useApp();
  const { user, isLoading: authLoading } = useAuth();
  const { token } = theme.useToken();

  // RBAC
  const canApprove = useMemo(() =>
    user?.profile?.toLowerCase() === 'dba' || user?.profile?.toLowerCase() === 'dbops',
    [user?.profile]
  );
  const canViewAll = canApprove;

  // Filters (Story 9.10)
  const { filters, applyFilters, resetFilters, activeFilterCount } = useExecutionFilters();

  // Data hook (Story 26.4 AC6)
  const {
    executions, loading, error, currentPage, setCurrentPage, totalCount,
    sortField, setSortField, sortOrder, setSortOrder,
    activeScope, setActiveScope, userHasChosenScope,
    statsData, statsLoading, timeSeriesData, timeSeriesLoading,
    pendingApprovals, pendingApprovalsLoading, loadPendingApprovals,
    integrationIconsMap, isRefreshingRef, refetchCurrentState, PAGE_SIZE,
  } = useExecutionsData(filters, canApprove);

  // Scope sync (Story 8.9)
  useEffect(() => {
    if (userHasChosenScope.current) return;
    if (authLoading) { if (activeScope !== 'mine') setActiveScope('mine'); return; }
    if (canViewAll && activeScope === 'mine') { setActiveScope('all'); return; }
    if (!canViewAll && activeScope === 'all') { setActiveScope('mine'); }
  }, [authLoading, canViewAll, activeScope, setActiveScope, userHasChosenScope]);

  // Drawer hook (Story 26.4 AC2)
  const {
    drawerOpen, selectedExecution, selectedSteps, selectedActionDetail,
    loading: drawerLoading, error: drawerError, openExecution, closeDrawer,
  } = useExecutionDetail();

  // Cancel state (Story 17.14)
  const isCancellingRef = useRef(false);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  // Restart hook (Story 26.4 AC3)
  const {
    restartWizardOpen, restartAction, restartAllowedEnvs, restartInitialParams,
    restartLoadingId, handleRestartExecution, handleRestartWizardClose, handleRestartSuccess,
  } = useExecutionRestart(refetchCurrentState, isRefreshingRef);

  // Cancel handler (Story 17.14)
  const handleCancelExecution = useCallback((executionId: number) => {
    if (isCancellingRef.current || cancellingId === executionId) {
      logger.debug('Cancel already in progress, ignoring duplicate', { executionId });
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
            try { await refetchCurrentState(); } finally { isRefreshingRef.current = false; }
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
  }, [modal, notification, refetchCurrentState, cancellingId, isRefreshingRef]);

  // Scope change (Story 8.9)
  const handleScopeChange = useCallback((scope: typeof activeScope) => {
    userHasChosenScope.current = true;
    setActiveScope(scope);
    setCurrentPage(1);
  }, [setActiveScope, setCurrentPage, userHasChosenScope]);

  // Approval complete (Story 8.8, 22.14)
  const handleApprovalComplete = useCallback(() => {
    loadPendingApprovals();
    if (!isRefreshingRef.current) {
      isRefreshingRef.current = true;
      refetchCurrentState().finally(() => { isRefreshingRef.current = false; });
    }
  }, [loadPendingApprovals, refetchCurrentState, isRefreshingRef]);

  // Execution grouping and sorting
  const { topLevelExecutions, childrenByParentId } = useMemo(() => {
    const childrenMap = new Map<number, ExecutionResponse[]>();
    for (const e of executions) {
      if (e.parent_execution_id != null) {
        const list = childrenMap.get(e.parent_execution_id) ?? [];
        list.push(e);
        childrenMap.set(e.parent_execution_id, list);
      }
    }
    for (const list of childrenMap.values()) {
      list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    }
    return { topLevelExecutions: executions.filter((e) => e.parent_execution_id == null), childrenByParentId: childrenMap };
  }, [executions]);

  const sortedExecutions = useMemo(() => {
    const sorted = [...topLevelExecutions];
    sorted.sort((a, b) => {
      const aRunning = isRunning(a.status) ? 0 : 1;
      const bRunning = isRunning(b.status) ? 0 : 1;
      if (aRunning !== bRunning) return aRunning - bRunning;
      let aVal: string | number | null = null;
      let bVal: string | number | null = null;
      if (sortField === 'created_at') { aVal = a.created_at; bVal = b.created_at; }
      else if (sortField === 'status') { aVal = a.status; bVal = b.status; }
      else if (sortField === 'action_name') { aVal = a.action_name || ''; bVal = b.action_name || ''; }
      if (aVal === null || bVal === null) return 0;
      if (aVal < bVal) return sortOrder === 'ascend' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'ascend' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [topLevelExecutions, sortField, sortOrder]);

  // Columns (Story 26.4 AC1)
  const columns = useMemo(() =>
    getExecutionsColumns(
      { onCancelExecution: handleCancelExecution, onRestartExecution: handleRestartExecution },
      { activeScope, sortField, sortOrder, integrationIconsMap, user, canViewAll, cancellingId, restartLoadingId },
    ),
    [activeScope, sortField, sortOrder, integrationIconsMap, user, canViewAll, cancellingId, handleCancelExecution, restartLoadingId, handleRestartExecution]
  );

  const handleTableChange = (
    pagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>,
    sorter: SorterResult<ExecutionResponse> | SorterResult<ExecutionResponse>[],
  ) => {
    if (pagination.current && pagination.current !== currentPage) setCurrentPage(pagination.current);
    const singleSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    if (singleSorter?.field) {
      setSortField(singleSorter.field as string);
      setSortOrder(singleSorter.order || 'descend');
    }
  };

  // Skeleton loading
  if (loading && executions.length === 0) {
    const skeletonColumns = [
      { title: 'Statut', key: 'status', width: 120, render: () => <Skeleton.Button active size="small" /> },
      { title: 'Action', key: 'action', width: 200, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Technologie', key: 'engine', width: 100, render: () => <Skeleton.Button active size="small" /> },
      { title: 'Plateforme', key: 'integration', width: 120, render: () => <Skeleton.Button active size="small" /> },
      ...(activeScope === 'all' ? [
        { title: 'Utilisateur', key: 'user', width: 150, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      ] : []),
      { title: 'Environnement', key: 'env', width: 120, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Date', key: 'date', width: 160, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Durée', key: 'duration', width: 100, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
    ];
    return (
      <div style={{ padding: 24 }}>
        <Title level={2}>Exécutions</Title>
        <Table columns={skeletonColumns} dataSource={Array.from({ length: 10 }, (_, i) => ({ key: i }))} rowKey="key" size="small" pagination={false} showHeader />
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

      <ExecutionsStatSection
        statsData={statsData} statsLoading={statsLoading}
        timeSeriesData={timeSeriesData} timeSeriesLoading={timeSeriesLoading} filters={filters}
      />

      <ExecutionsFiltersPanel
        filters={filters} onApplyFilters={applyFilters}
        onResetFilters={resetFilters} activeFilterCount={activeFilterCount} loading={loading}
      />

      {canApprove && pendingApprovals.length > 0 && (
        <Card
          id="pending-approvals"
          title={<Space><SafetyCertificateOutlined style={{ color: token.colorWarning }} /><span>Approbations en attente</span><Tag color="warning">{pendingApprovals.length}</Tag></Space>}
          style={{ marginBottom: 24, borderColor: token.colorWarning }}
        >
          <PendingApprovalsList executions={pendingApprovals} loading={pendingApprovalsLoading} onActionComplete={handleApprovalComplete} />
        </Card>
      )}

      <ExecutionsTabs activeScope={activeScope} onScopeChange={handleScopeChange} canViewAll={canViewAll} />

      <Table<ExecutionResponse>
        dataSource={sortedExecutions} columns={columns} rowKey="id" size="small" loading={loading}
        pagination={{ current: currentPage, pageSize: PAGE_SIZE, total: totalCount, showSizeChanger: false }}
        onChange={handleTableChange}
        onRow={(record) => ({ onClick: () => openExecution(record), style: { cursor: 'pointer' } })}
        expandable={{
          rowExpandable: (record) => record.item_type === 'workflow' && (childrenByParentId.get(record.id)?.length ?? 0) > 0,
          expandedRowRender: (record) => {
            const children = childrenByParentId.get(record.id) ?? [];
            if (children.length === 0) return null;
            return (
              <div style={{ padding: '8px 0 8px 24px', background: token.colorFillQuaternary }}>
                <Typography.Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                  Actions du workflow ({children.length})
                </Typography.Text>
                <Table<ExecutionResponse>
                  dataSource={children} rowKey="id" size="small" pagination={false} showHeader
                  onRow={(c) => ({ onClick: (e) => { e.stopPropagation(); openExecution(c); }, style: { cursor: 'pointer' } })}
                  columns={columns}
                />
              </div>
            );
          },
        }}
        locale={{ emptyText: 'Aucune exécution trouvée' }}
      />

      <ExecutionDetailDrawer
        open={drawerOpen} execution={selectedExecution} steps={selectedSteps}
        actionDetail={selectedActionDetail} loading={drawerLoading} error={drawerError}
        onClose={closeDrawer} onExecutionUpdate={() => {}}
      />

      <ExecutionWizard
        open={restartWizardOpen} action={restartAction} allowedEnvironments={restartAllowedEnvs}
        onCancel={handleRestartWizardClose} onSuccess={handleRestartSuccess} initialParams={restartInitialParams}
      />
    </div>
  );
}
