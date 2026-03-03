/**
 * AuditTable — Story 34.11 (SOLID-FE-3), Story 43.4
 *
 * Table des entrées d'audit avec colonnes, pagination, tri, et expandable rows workflow.
 * Story 43.4 : colonnes Type, Opération, Entité, Catégorie + contrôle de visibilité.
 */

import { useState } from 'react';
import { Typography, Table, Tag, Space, Popover, Checkbox, Button } from 'antd';
import type { TableProps } from 'antd';
import { CheckCircleOutlined, TableOutlined } from '@ant-design/icons';
import type {
  AuditExecutionEntry,
  PaginationInfo,
} from '../../types/api';
import { ACTION_TYPE_LABELS } from '../../constants/auditActionTypes';
import { AUDIT_STATUS_CONFIG as STATUS_CONFIG } from '../../utils/execution-status';
import { ENTITY_TYPE_LABELS, formatDate, getEntityLabel } from './auditLabels';
import { getEnvironmentLabel } from '../../utils/environmentHelpers';
import { getOperationConfig } from './auditTableOperations';

const { Text } = Typography;

const PAGE_SIZE_OPTIONS = [25, 50, 100];

type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;

// ─── Column visibility ────────────────────────────────────────────────────────

const COLUMN_VISIBILITY_OPTIONS = [
  { label: 'Entité', value: 'entity' },
  { label: 'Type', value: 'type' },
  { label: 'Opération', value: 'operation' },
  { label: 'Utilisateur', value: 'user_id' },
  { label: 'Catégorie', value: 'category' },
  { label: 'Environnement', value: 'environment' },
  { label: 'Statut', value: 'status' },
  { label: 'Date', value: 'timestamp' },
  { label: 'Change SN', value: 'servicenow' },
];

// ─── Props ────────────────────────────────────────────────────────────────────

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

// ─── Component ────────────────────────────────────────────────────────────────

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
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(
    new Set(['category', 'environment', 'servicenow']),
  );

  const allColumns: TableProps<AuditExecutionEntry>['columns'] = [
    {
      title: 'Entité',
      key: 'entity',
      sorter: true,
      sortOrder: sortField === 'entity' ? sortOrder : undefined,
      render: (_: unknown, record: AuditExecutionEntry) => getEntityLabel(record),
    },
    {
      title: 'Type',
      key: 'type',
      render: (_: unknown, record: AuditExecutionEntry) =>
        ACTION_TYPE_LABELS[record.action_type] ?? record.action_type,
    },
    {
      title: 'Opération',
      key: 'operation',
      width: 130,
      render: (_: unknown, record: AuditExecutionEntry) => {
        const op = getOperationConfig(record.action_type);
        if (!op.icon && op.label === '—') return <span>—</span>;
        return (
          <Space size={4}>
            <span style={{ color: op.color }}>{op.icon}</span>
            <span>{op.label}</span>
          </Space>
        );
      },
    },
    {
      title: 'Utilisateur',
      dataIndex: 'user_name',
      key: 'user_id',
      width: 140,
      render: (_: string | null, record: AuditExecutionEntry) => {
        if (record.action_type === 'EXECUTION_APPROVED') {
          return (
            <Tag icon={<CheckCircleOutlined />} color="green">
              Approuvé par {record.user_name ?? record.user_id}
            </Tag>
          );
        }
        return record.user_name ?? record.user_id ?? '—';
      },
    },
    {
      title: 'Catégorie',
      key: 'category',
      width: 140,
      render: (_: unknown, record: AuditExecutionEntry) =>
        ENTITY_TYPE_LABELS[record.entity_type] ?? record.entity_type,
    },
    {
      title: 'Environnement',
      key: 'environment',
      width: 120,
      render: (_: unknown, record: AuditExecutionEntry) =>
        record.entity_type !== 'execution' ? (
          <span>—</span>
        ) : (
          <span>{getEnvironmentLabel(record.details?.environment ?? '') || '—'}</span>
        ),
    },
    {
      title: 'Statut',
      key: 'status',
      width: 100,
      render: (_: unknown, record: AuditExecutionEntry) => {
        if (record.entity_type !== 'execution') return <span>—</span>;
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
        if (record.entity_type !== 'execution') return '—';
        const changeId = record.details?.servicenow_change_id;
        return changeId ? (
          <Text copyable={{ text: String(changeId) }}>{String(changeId).slice(0, 10)}...</Text>
        ) : (
          '—'
        );
      },
    },
  ];

  const columns = allColumns.filter((col) => !hiddenColumns.has(col.key as string));

  const visibleValues = COLUMN_VISIBILITY_OPTIONS.map((o) => o.value).filter(
    (v) => !hiddenColumns.has(v),
  );

  const columnToggle = (
    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
      <Popover
        title="Colonnes visibles"
        content={
          <Checkbox.Group
            options={COLUMN_VISIBILITY_OPTIONS}
            value={visibleValues}
            onChange={(checked) => {
              const allKeys = COLUMN_VISIBILITY_OPTIONS.map((o) => o.value);
              const newHidden = new Set(allKeys.filter((k) => !(checked as string[]).includes(k)));
              setHiddenColumns(newHidden);
            }}
            style={{ display: 'flex', flexDirection: 'column', gap: 4 }}
          />
        }
        trigger="click"
      >
        <Button icon={<TableOutlined />} size="small">
          Colonnes
        </Button>
      </Popover>
    </div>
  );

  return (
    <>
      {columnToggle}
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
    </>
  );
}

