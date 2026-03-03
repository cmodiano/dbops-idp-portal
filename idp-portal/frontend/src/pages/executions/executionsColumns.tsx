/**
 * ExecutionsPage Table Columns Definitions
 *
 * Story 26.4 - AC1: Extracted from ExecutionsPage.tsx to separate concerns.
 * Defines all 9 columns for the executions table with handlers and state.
 * Pattern: pages/admin/actionsColumns.tsx
 */
/* eslint-disable react-refresh/only-export-components */
import { Button, Space, Tooltip } from 'antd';
import { RedoOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { TableProps } from 'antd';
import {
  renderStatusIndicator,
  renderEngineIcon,
  renderPlateformeIcon,
} from '../../utils/executionRenderers';
import { formatUtcToLocal } from '../../utils/dateFormat';
import { getEnvironmentLabel } from '../../utils/environmentHelpers';
import type { IntegrationIconsMap } from '../../utils/executionRenderers';
import type {
  ExecutionResponse,
  ExecutionStatusType,
  ExecutionScope,
} from '../../types/api';
import type { User } from '../../types/common';
import { RUNNING_STATUSES } from '../../constants/executions';

/** Re-export for tests and consumers that import from this module. */
export { RUNNING_STATUSES };

/** Format duration from ISO timestamps. */
export function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return '—';
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return remaining ? `${minutes}m ${remaining}s` : `${minutes}m`;
}

/** Format UTC date for display in local timezone (API dates are UTC with Z suffix). */
export function formatDate(dateStr: string | null): string {
  return formatUtcToLocal(dateStr, 'datetime');
}

/** Check if execution is in a running state (AC3). */
export function isRunning(status: ExecutionStatusType): boolean {
  return RUNNING_STATUSES.includes(status);
}

/** Handlers passed to column definitions. */
export interface ExecutionColumnHandlers {
  onCancelExecution: (id: number) => void;
  onRestartExecution: (execution: ExecutionResponse) => void;
}

/** State required for column rendering. */
export interface ExecutionColumnState {
  activeScope: ExecutionScope;
  sortField: string;
  sortOrder: 'ascend' | 'descend';
  integrationIconsMap: IntegrationIconsMap | null;
  user: User | null;
  canViewAll: boolean;
  /** Whether the user can manage (cancel/restart) other users' executions (DBA/DBOPS only). */
  canManage: boolean;
  cancellingId: number | null;
  restartLoadingId: number | null;
}

/**
 * Get ExecutionsPage table columns configuration.
 *
 * @param handlers - Event handlers for column actions
 * @param state - Current state for conditional rendering
 * @param theme - Ant Design theme tokens
 * @returns Table columns array
 */
export const getExecutionsColumns = (
  handlers: ExecutionColumnHandlers,
  state: ExecutionColumnState,
): TableProps<ExecutionResponse>['columns'] => {
  const baseColumns: TableProps<ExecutionResponse>['columns'] = [
    // Story 9.9 AC1: Colonne Statut en première position
    {
      title: 'Statut',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      align: 'center' as const,
      render: (status: ExecutionStatusType) => renderStatusIndicator(status),
      sorter: false,
    },
    // Story 9.9 AC7: Colonne Action
    {
      title: 'Action',
      dataIndex: 'action_name',
      key: 'action_name',
      sorter: true,
      sortOrder: state.sortField === 'action_name' ? state.sortOrder : undefined,
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
      sorter: false,
    },
    // Story 9.9 AC5: Colonne Plateforme
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
          state.integrationIconsMap,
        ),
      sorter: false,
    },
  ];

  // Story 8.9 AC9: Add "Utilisateur" column only for scope=all
  if (state.activeScope === 'all') {
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
      render: (env: string) => getEnvironmentLabel(env || '') || '—',
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      sorter: true,
      sortOrder: state.sortField === 'created_at' ? state.sortOrder : undefined,
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
    // Story 17.14, 17.15: Colonne Actions avec boutons Annuler et Relancer
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      align: 'center' as const,
      render: (_: unknown, record: ExecutionResponse) => {
        const isCancellable = record.status === 'SUBMITTED' || record.status === 'RUNNING';
        const isOwner = record.user_id === state.user?.id;
        const canCancel = isCancellable && (isOwner || state.canManage);
        const canRestart = isOwner || state.canManage;

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
                  loading={state.restartLoadingId === record.id}
                  onClick={(e) => { e.stopPropagation(); handlers.onRestartExecution(record); }}
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
                  loading={state.cancellingId === record.id}
                  onClick={(e) => { e.stopPropagation(); handlers.onCancelExecution(record.id); }}
                />
              </Tooltip>
            )}
          </Space>
        );
      },
    },
  );

  return baseColumns;
};
