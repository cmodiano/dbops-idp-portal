/**
 * AuditTable — Story 34.11 (SOLID-FE-3)
 *
 * Table des entrées d'audit avec colonnes, pagination, tri, et expandable rows workflow.
 * Extrait de AuditPage.tsx.
 */

import { Typography, Table, Tag } from 'antd';
import type { TableProps } from 'antd';
import type {
  AuditExecutionEntry,
  PaginationInfo,
} from '../../types/api';
import { AUDIT_STATUS_CONFIG as STATUS_CONFIG } from '../../utils/execution-status';

const { Text } = Typography;

const PAGE_SIZE_OPTIONS = [25, 50, 100];

type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;

/** Format date for display. */
// eslint-disable-next-line react-refresh/only-export-components
export function formatDate(dateStr: string | null): string {
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

/** Extract action name from entry (enriched by backend) or fallback. */
// eslint-disable-next-line react-refresh/only-export-components
export function getActionName(entry: AuditExecutionEntry): string {
  if (entry.action_name) {
    return entry.action_name;
  }
  const actionId = entry.details?.action_id;
  return actionId ? `Action #${actionId}` : 'Action inconnue';
}

export interface AuditTableProps {
  topLevelEntries: AuditExecutionEntry[];
  childrenByParentId: Map<number, AuditExecutionEntry[]>;
  loading: boolean;
  pagination: PaginationInfo | null;
  currentPage: number;
  pageSize: number;
  sortField: string;
  sortOrder: 'ascend' | 'descend';
  onChange: TableOnChange<AuditExecutionEntry>;
  onRowClick: (record: AuditExecutionEntry) => void;
}

export function AuditTable({
  topLevelEntries,
  childrenByParentId,
  loading,
  pagination,
  currentPage,
  pageSize,
  sortField,
  sortOrder,
  onChange,
  onRowClick,
}: AuditTableProps) {
  const columns: TableProps<AuditExecutionEntry>['columns'] = [
    {
      title: 'Action',
      key: 'action',
      sorter: true,
      sortOrder: sortField === 'action' ? sortOrder : undefined,
      render: (_: unknown, record: AuditExecutionEntry) => getActionName(record),
    },
    {
      title: 'Utilisateur',
      dataIndex: 'user_name',
      key: 'user_id',
      width: 140,
      render: (_: string | null, record: AuditExecutionEntry) =>
        record.user_name ?? record.user_id ?? '—',
    },
    {
      title: 'Environnement',
      key: 'environment',
      width: 120,
      render: (_: unknown, record: AuditExecutionEntry) => (
        <span>{record.details?.environment?.toUpperCase() || '—'}</span>
      ),
    },
    {
      title: 'Statut',
      key: 'status',
      width: 100,
      render: (_: unknown, record: AuditExecutionEntry) => {
        const config = STATUS_CONFIG[record.derived_status] || STATUS_CONFIG.unknown;
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: 'Date',
      dataIndex: 'timestamp',
      key: 'timestamp',
      sorter: true,
      sortOrder: sortField === 'timestamp' ? sortOrder : undefined,
      width: 160,
      render: (date: string) => formatDate(date),
    },
    {
      title: 'Change SN',
      key: 'servicenow',
      width: 130,
      render: (_: unknown, record: AuditExecutionEntry) => {
        const changeId = record.details?.servicenow_change_id;
        return changeId ? (
          <Text copyable={{ text: String(changeId) }}>{String(changeId).slice(0, 10)}...</Text>
        ) : (
          '—'
        );
      },
    },
  ];

  return (
    <Table<AuditExecutionEntry>
      dataSource={topLevelEntries}
      columns={columns}
      rowKey="id"
      loading={loading}
      pagination={{
        current: currentPage,
        pageSize,
        total: pagination?.total || 0,
        showSizeChanger: true,
        pageSizeOptions: PAGE_SIZE_OPTIONS.map(String),
      }}
      onChange={onChange}
      onRow={(record) => ({
        onClick: () => onRowClick(record),
        style: { cursor: 'pointer' },
      })}
      expandable={{
        rowExpandable: (record) =>
          record.item_type === 'workflow' &&
          (childrenByParentId.get(record.entity_id)?.length ?? 0) > 0,
        expandedRowRender: (record) => {
          const children = childrenByParentId.get(record.entity_id) ?? [];
          if (children.length === 0) return null;
          return (
            <div style={{ padding: '8px 0 8px 24px' }}>
              <Text type="secondary" style={{ fontSize: 12, marginBottom: 8, display: 'block' }}>
                Actions du workflow ({children.length})
              </Text>
              <Table<AuditExecutionEntry>
                dataSource={children}
                rowKey="id"
                size="small"
                pagination={false}
                showHeader={false}
                onRow={(childRecord) => ({
                  onClick: (e) => {
                    e.stopPropagation();
                    onRowClick(childRecord);
                  },
                  style: { cursor: 'pointer' },
                })}
                columns={columns}
              />
            </div>
          );
        },
      }}
      locale={{
        emptyText: "Aucune entrée d'audit trouvée",
      }}
    />
  );
}
