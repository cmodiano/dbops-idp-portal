/**
 * RecentExecutions - Dashboard recent activity table (Story 5.1, Task 3.2; Story 9.9 refactor).
 *
 * Displays the 10 most recent executions with columns:
 * action, user, environment, status, date.
 *
 * AC2: Table shows executions from ALL users (DBA visibility).
 * Story 9.9 AC8: Uses shared executionRenderers for engine/platform icons.
 */

import { Table, Skeleton, Typography, App, Avatar } from 'antd';
import {
  ClockCircleOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { useEffect, useRef, useState } from 'react';
import type { TableProps } from 'antd';
import type { DashboardRecentExecution, ExecutionStatusType } from '../../types/api';
import type { ActionEngine } from '../../types/api';
import {
  STATUS_CONFIG,
  ENGINE_ICONS_CONFIG,
  ENGINE_ICON_SIZE_VALUE,
  ENGINE_SVG_SOURCES,
} from '../../utils/executionRenderers';
import { getIconUrl } from '../../utils/iconUrl';

const { Text } = Typography;

/** Engine icon size for this component (matches shared config). */
const ENGINE_ICON_SIZE = ENGINE_ICON_SIZE_VALUE;

/** Format date for display. */
function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Map integration type (platform or engine name) → icon URL for display. From integrations list. */
export type IntegrationIconsByType = Record<string, string | null>;

export interface RecentExecutionsProps {
  /** List of recent executions to display. */
  executions: DashboardRecentExecution[];
  /** Whether the table is in loading state. */
  loading?: boolean;
  /** Callback when a row is clicked (to open drawer). */
  onRowClick?: (execution: DashboardRecentExecution) => void;
  /** Set of execution IDs to highlight (Story 5.2, AC3 - FAILED rows). */
  highlightedIds?: Set<number>;
  /** Optional map: integration type (platform name) → icon URL. Used for Plateforme column only. */
  integrationIconsByType?: IntegrationIconsByType;
}

/** Render Technologie column: engine icon + name (Oracle, SQL Server, DB2).
 * Story 9.9 AC8: Uses ENGINE_ICONS_CONFIG and ENGINE_SVG_SOURCES from shared executionRenderers. */
function EngineIconCell({ engine }: { engine: string | null | undefined }) {
  if (!engine) {
    return <span style={{ opacity: 0.4 }}>—</span>;
  }
  const config = ENGINE_ICONS_CONFIG[engine as ActionEngine];
  const svgSrc = ENGINE_SVG_SOURCES[engine as ActionEngine];
  if (!config) {
    return <span title={engine} style={{ fontSize: 12, opacity: 0.6 }}>{engine}</span>;
  }
  const iconNode = svgSrc ? (
    <img
      src={svgSrc}
      alt=""
      width={ENGINE_ICON_SIZE}
      height={ENGINE_ICON_SIZE}
      style={{ flexShrink: 0 }}
      aria-hidden
    />
  ) : (
    <config.Icon style={{ fontSize: ENGINE_ICON_SIZE, color: config.color, flexShrink: 0 }} aria-hidden />
  );
  return (
    <span
      title={engine}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}
    >
      {iconNode}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{engine}</span>
    </span>
  );
}

/** Render Plateforme column: integration icon + name when available. */
function IntegrationIconCell({
  type,
  title,
  integrationIconsByType,
}: {
  type: string | null | undefined;
  title?: string;
  integrationIconsByType?: IntegrationIconsByType;
}) {
  const rawIconUrl = type ? integrationIconsByType?.[type] : undefined;
  const iconSrc = getIconUrl(rawIconUrl);
  const label = type ?? '—';
  return (
    <span
      title={title ?? label}
      style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12 }}
    >
      {iconSrc ? (
        <Avatar src={iconSrc} shape="square" size={20} icon={<ApiOutlined />} style={{ flexShrink: 0 }} />
      ) : (
        <Avatar shape="square" size={20} icon={<ApiOutlined />} style={{ opacity: type ? 0.7 : 0.4, flexShrink: 0 }} />
      )}
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
    </span>
  );
}

export function RecentExecutions({
  executions,
  loading = false,
  onRowClick,
  highlightedIds,
  integrationIconsByType,
}: RecentExecutionsProps) {
  const { message } = App.useApp();
  // Track previous executions for aria-live announcements (Story 5.2, AC5)
  const prevExecutionsRef = useRef<DashboardRecentExecution[]>([]);
  // Dedicated live region text for screen readers (code-review AC5)
  const [liveAnnouncement, setLiveAnnouncement] = useState<string | null>(null);

  // Announce status changes for screen readers (Story 5.2, AC5)
  useEffect(() => {
    if (loading) return;

    const prevExecutions = prevExecutionsRef.current;
    let lastAnnouncement: string | null = null;
    for (const exec of executions) {
      const prevExec = prevExecutions.find((e) => e.id === exec.id);
      if (prevExec && prevExec.status !== exec.status) {
        const statusLabel = STATUS_CONFIG[exec.status]?.label || exec.status;
        const text = `Exécution ${exec.action_name || `#${exec.id}`} mise à jour : ${statusLabel}`;
        lastAnnouncement = text;
        message.info({
          content: text,
          key: `exec-update-${exec.id}`,
          duration: 3,
        });
      }
    }
    if (lastAnnouncement) {
      queueMicrotask(() => setLiveAnnouncement(lastAnnouncement));
      const t = setTimeout(() => setLiveAnnouncement(null), 1000);
      prevExecutionsRef.current = executions;
      return () => clearTimeout(t);
    }
    prevExecutionsRef.current = executions;
  }, [executions, loading, message]);
  const columns: TableProps<DashboardRecentExecution>['columns'] = [
    {
      title: '',
      dataIndex: 'status',
      key: 'status',
      width: 44,
      align: 'center',
      render: (status: ExecutionStatusType) => {
        const config = STATUS_CONFIG[status] ?? {
          label: status,
          Icon: ClockCircleOutlined,
          color: '#9CA3AF',
        };
        const isRunning = status === 'RUNNING';
        return (
          <span
            title={config.label}
            style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <config.Icon
              spin={isRunning}
              style={{ fontSize: 18, color: config.color }}
              aria-label={config.label}
            />
          </span>
        );
      },
    },
    {
      title: 'Technologie',
      dataIndex: 'engine',
      key: 'engine',
      width: 120,
      ellipsis: true,
      render: (engine: string | null | undefined) => <EngineIconCell engine={engine} />,
    },
    {
      title: 'Action',
      dataIndex: 'action_name',
      key: 'action_name',
      ellipsis: true,
      render: (name: string | null, record: DashboardRecentExecution) => (
        <Text strong>{name || `Action #${record.id}`}</Text>
      ),
    },
    {
      title: 'Plateforme',
      dataIndex: 'platform',
      key: 'platform',
      width: 140,
      ellipsis: true,
      render: (platform: string | null | undefined) => (
        <IntegrationIconCell
          type={platform ?? undefined}
          title={platform ?? undefined}
          integrationIconsByType={integrationIconsByType}
        />
      ),
    },
    {
      title: 'Utilisateur',
      dataIndex: 'user_display_name',
      key: 'user_display_name',
      width: 140,
      ellipsis: true,
    },
    {
      title: 'Env',
      dataIndex: 'environment',
      key: 'environment',
      width: 80,
      render: (env: string) => env?.toUpperCase() || '—',
    },
    {
      title: 'Date',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 100,
      render: (date: string | null) => formatDate(date),
    },
  ];

  // Skeleton rows during loading (AC6, Task 3.3)
  if (loading) {
    const skeletonColumns = [
      { title: '', key: 'status', width: 44, render: () => <Skeleton.Button active size="small" /> },
      { title: 'Technologie', key: 'engine', width: 120, render: () => <Skeleton active title={false} paragraph={{ rows: 1, width: '80%' }} /> },
      { title: 'Action', key: 'action', render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Plateforme', key: 'platform', width: 140, render: () => <Skeleton active title={false} paragraph={{ rows: 1, width: '80%' }} /> },
      { title: 'Utilisateur', key: 'user', width: 140, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Env', key: 'env', width: 80, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Date', key: 'date', width: 100, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
    ];
    const skeletonData = Array.from({ length: 10 }, (_, i) => ({ key: i }));
    return (
      <Table
        columns={skeletonColumns}
        dataSource={skeletonData}
        rowKey="key"
        pagination={false}
        size="small"
      />
    );
  }

  return (
    <div>
      {/* Dedicated aria-live region for screen readers (Story 5.2, AC5 — code-review) */}
      <div
        aria-live="polite"
        aria-atomic="true"
        role="status"
        style={{
          position: 'absolute',
          width: 1,
          height: 1,
          padding: 0,
          margin: -1,
          overflow: 'hidden',
          clip: 'rect(0,0,0,0)',
          whiteSpace: 'nowrap',
          border: 0,
        }}
      >
        {liveAnnouncement}
      </div>
      <Table<DashboardRecentExecution>
        dataSource={executions}
        columns={columns}
        rowKey="id"
        pagination={false}
        size="small"
        locale={{
          emptyText: 'Aucune exécution récente',
        }}
        onRow={(record) => {
          const isHighlighted = record.status === 'FAILED' || highlightedIds?.has(record.id);
          return {
            onClick: () => onRowClick?.(record),
            style: {
              cursor: onRowClick ? 'pointer' : undefined,
              // Story 5.2, AC3: Subtle red highlight for FAILED rows
              backgroundColor: isHighlighted ? 'rgba(255, 77, 79, 0.08)' : undefined,
            },
          };
        }}
      />
    </div>
  );
}

export default RecentExecutions;
