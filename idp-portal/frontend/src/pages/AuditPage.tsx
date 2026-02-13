/**
 * AuditPage - Consultation historique d'audit (Story 6.3).
 *
 * AC1: Table with columns: action, user, environment, status, date, ServiceNow change.
 * AC2: Filters: period, environment, action, user, status (real-time).
 * AC3: Drawer with full details: who, what, when, parameters, result, logs, timeline.
 * AC4: Sortable columns (click header).
 * AC5: Pagination 25 per page.
 * AC8: Access restricted to auditors (is_auditor=true).
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Typography,
  Table,
  Drawer,
  Tag,
  Skeleton,
  Alert,
  DatePicker,
  Select,
  Space,
  Card,
  Descriptions,
  Badge,
  Button,
  App,
  Dropdown,
} from 'antd';
import type { MenuProps } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import type { TableProps, TablePaginationConfig } from 'antd';
import dayjs, { type Dayjs } from 'dayjs';
import { listExecutionAudit, exportAuditReport } from '../services/audit_service';
import { getExecution, getExecutionSteps } from '../services/execution_service';
import { ExecutionTimeline } from '../components/execution/ExecutionTimeline';
import { useAuth } from '../contexts/AuthContext';
import type {
  AuditExecutionEntry,
  AuditStatusFilter,
  ExecutionResponse,
  ExecutionStepResponse,
  PaginationInfo,
} from '../types/api';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const PAGE_SIZE = 25;

// Ant Design 6.2: Extract table event types
type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;

/** Status colors for Tag display (AC1). */
const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  success: { color: 'success', label: 'Succès' },
  failed: { color: 'error', label: 'Échec' },
  running: { color: 'processing', label: 'En cours' },
  unknown: { color: 'default', label: 'Inconnu' },
};

/** Environment options for filter. */
const ENVIRONMENT_OPTIONS = [
  { value: 'dev', label: 'DEV' },
  { value: 'staging', label: 'STAGING' },
  { value: 'prod', label: 'PROD' },
];

/** Status options for filter. */
const STATUS_OPTIONS: { value: AuditStatusFilter; label: string }[] = [
  { value: 'success', label: 'Succès' },
  { value: 'failed', label: 'Échec' },
  { value: 'running', label: 'En cours' },
];

/** Period presets for date picker. */
const PERIOD_PRESETS: { label: string; value: [Dayjs, Dayjs] }[] = [
  { label: '7 derniers jours', value: [dayjs().subtract(7, 'day'), dayjs()] },
  { label: '30 derniers jours', value: [dayjs().subtract(30, 'day'), dayjs()] },
  { label: '90 derniers jours', value: [dayjs().subtract(90, 'day'), dayjs()] },
];

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

/** Extract action name from entry (enriched by backend) or fallback. */
function getActionName(entry: AuditExecutionEntry): string {
  // Prefer enriched action_name from backend (Story 6.3, HIGH-4 fix)
  if (entry.action_name) {
    return entry.action_name;
  }
  // Fallback to action_id if name not available
  const actionId = entry.details?.action_id;
  return actionId ? `Action #${actionId}` : 'Action inconnue';
}

export default function AuditPage() {
  const { message } = App.useApp();
  const { user } = useAuth();

  // Table data
  const [entries, setEntries] = useState<AuditExecutionEntry[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters (AC2)
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null]>([null, null]);
  const [environment, setEnvironment] = useState<string | undefined>();
  const [status, setStatus] = useState<AuditStatusFilter | undefined>();
  const [currentPage, setCurrentPage] = useState(1);
  const [sortField, setSortField] = useState<string>('timestamp');
  const [sortOrder, setSortOrder] = useState<'ascend' | 'descend'>('descend');

  // Drawer state (AC3)
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<AuditExecutionEntry | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResponse | null>(null);
  const [selectedSteps, setSelectedSteps] = useState<ExecutionStepResponse[]>([]);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [drawerError, setDrawerError] = useState<string | null>(null);

  // Fetch data (AC2, AC5)
  const fetchData = useCallback(async (page: number) => {
    setLoading(true);
    setError(null);
    try {
      const offset = (page - 1) * PAGE_SIZE;
      // Map frontend sort field names to API sort field names
      const apiSortField = sortField === 'action' ? 'action_type' : sortField;
      const apiSortOrder = sortOrder === 'ascend' ? 'asc' : 'desc';

      const result = await listExecutionAudit({
        from: dateRange[0]?.startOf('day').toISOString(),
        to: dateRange[1]?.endOf('day').toISOString(),
        environment,
        status,
        sort: apiSortField,
        order: apiSortOrder,
        limit: PAGE_SIZE,
        offset,
      });
      setEntries(result.data);
      setPagination(result.pagination);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement');
    } finally {
      setLoading(false);
    }
  }, [dateRange, environment, status, sortField, sortOrder]);

  // Initial load and filter changes
  useEffect(() => {
    fetchData(currentPage);
  }, [fetchData, currentPage]);

  // Reset to page 1 when filters or sort change
  useEffect(() => {
    setCurrentPage(1);
  }, [dateRange, environment, status, sortField, sortOrder]);

  // Open drawer with details (AC3)
  const handleRowClick = async (record: AuditExecutionEntry) => {
    setDrawerOpen(true);
    setDrawerLoading(true);
    setDrawerError(null);
    setSelectedEntry(record);
    setSelectedExecution(null);
    setSelectedSteps([]);

    try {
      // Fetch execution details if entity_id is available
      if (record.entity_id) {
        const [execution, steps] = await Promise.all([
          getExecution(record.entity_id),
          getExecutionSteps(record.entity_id),
        ]);
        setSelectedExecution(execution);
        setSelectedSteps(steps);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Erreur de chargement du détail';
      setDrawerError(message);
    } finally {
      setDrawerLoading(false);
    }
  };

  // Table change handler (AC4, AC5)
  const handleTableChange: TableOnChange<AuditExecutionEntry> = (
    paginationConfig,
    _filters,
    sorter,
  ) => {
    if (paginationConfig.current && paginationConfig.current !== currentPage) {
      setCurrentPage(paginationConfig.current);
    }

    const singleSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    if (singleSorter?.field) {
      setSortField(singleSorter.field as string);
      setSortOrder(singleSorter.order || 'descend');
    }
  };

  // Export handler (Story 6.4, AC1, AC2, AC3, AC5)
  const [exporting, setExporting] = useState(false);
  const handleExport = async (format: 'csv' | 'pdf') => {
    setExporting(true);
    try {
      // Pass all available filters to export (Story 6.4, MEDIUM-3 fix)
      await exportAuditReport(format, {
        from: dateRange[0]?.startOf('day').toISOString(),
        to: dateRange[1]?.endOf('day').toISOString(),
        environment,
        status,
        // Note: action_id and user_id filters not yet in UI but passed for future compatibility
        action_id: undefined,
        user_id: undefined,
      });
      message.success('Rapport exporté — Télécharger', 3);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Erreur lors de l\'export';
      message.error(errorMessage, 5);
    } finally {
      setExporting(false);
    }
  };

  const exportMenuItems: MenuProps['items'] = [
    {
      key: 'csv',
      label: 'CSV',
      onClick: () => handleExport('csv'),
    },
    {
      key: 'pdf',
      label: 'PDF',
      onClick: () => handleExport('pdf'),
    },
  ];

  // Table columns (AC1, AC4)
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
      dataIndex: 'user_id',
      key: 'user_id',
      width: 120,
      render: (userId: string) => userId || '—',
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
    // Top-level = entries without parent_execution_id
    const topLevel = entries.filter((e) => e.parent_execution_id == null);
    return { topLevelEntries: topLevel, childrenByParentId: childrenMap };
  }, [entries]);

  // Access check (AC8)
  if (!user?.is_auditor) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={2}>Audit</Title>
        <Alert
          type="error"
          message="Accès non autorisé"
          description="Cette page est réservée aux auditeurs."
          showIcon
        />
      </div>
    );
  }

  // Skeleton loading (AC5)
  if (loading && entries.length === 0) {
    const skeletonColumns = [
      { title: 'Action', key: 'action', render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Utilisateur', key: 'user', width: 120, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Environnement', key: 'env', width: 120, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Statut', key: 'status', width: 100, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Date', key: 'date', width: 160, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
      { title: 'Change SN', key: 'sn', width: 130, render: () => <Skeleton active title={false} paragraph={{ rows: 1 }} /> },
    ];
    const skeletonData = Array.from({ length: 10 }, (_, i) => ({ key: i }));
    return (
      <div style={{ padding: 24 }}>
        <Title level={2}>Audit des exécutions</Title>
        <Table columns={skeletonColumns} dataSource={skeletonData} rowKey="key" pagination={false} />
      </div>
    );
  }

  if (error && entries.length === 0) {
    return (
      <div style={{ padding: 24 }}>
        <Title level={2}>Audit des exécutions</Title>
        <Alert type="error" message="Erreur" description={error} showIcon />
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Audit des exécutions</Title>

      {/* Filters (AC2) */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <Space wrap>
            <RangePicker
              presets={PERIOD_PRESETS}
              value={dateRange}
              onChange={(dates) => setDateRange(dates || [null, null])}
              placeholder={['Date début', 'Date fin']}
              allowClear
            />
            <Select
              placeholder="Environnement"
              aria-label="Filtre Environnement"
              options={ENVIRONMENT_OPTIONS}
              value={environment}
              onChange={setEnvironment}
              allowClear
              style={{ width: 140 }}
              data-testid="audit-filter-environment"
            />
            <Select
              placeholder="Statut"
              options={STATUS_OPTIONS}
              value={status}
              onChange={setStatus}
              allowClear
              style={{ width: 120 }}
            />
            {pagination && (
              <Badge
                count={pagination.total}
                overflowCount={99999}
                style={{ backgroundColor: '#1890ff' }}
                showZero
              >
                <Text type="secondary" style={{ marginLeft: 8 }}>
                  résultats
                </Text>
              </Badge>
            )}
          </Space>
          {/* Export button — aligned right */}
          <Dropdown menu={{ items: exportMenuItems }} trigger={['click']}>
            <Button icon={<DownloadOutlined />} loading={exporting}>
              Exporter
            </Button>
          </Dropdown>
        </div>
      </Card>

      {/* Table (AC1, AC4, AC5) — with workflow accordion grouping */}
      <Table<AuditExecutionEntry>
        dataSource={topLevelEntries}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{
          current: currentPage,
          pageSize: PAGE_SIZE,
          total: pagination?.total || 0,
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
          emptyText: 'Aucune entrée d\'audit trouvée',
        }}
      />

      {/* Drawer with details (AC3) */}
      <Drawer
        title="Détail d'audit"
        open={drawerOpen}
        onClose={() => {
          setDrawerOpen(false);
          setDrawerError(null);
        }}
        width={600}
        destroyOnClose
      >
        {drawerLoading ? (
          <Skeleton active paragraph={{ rows: 8 }} />
        ) : drawerError ? (
          <Alert type="error" message="Erreur de chargement" description={drawerError} showIcon />
        ) : selectedEntry ? (
          <div>
            {/* Audit entry details */}
            <Descriptions bordered column={1} size="small" style={{ marginBottom: 24 }}>
              <Descriptions.Item label="Qui">{selectedEntry.user_id || '—'}</Descriptions.Item>
              <Descriptions.Item label="Quoi">{getActionName(selectedEntry)}</Descriptions.Item>
              <Descriptions.Item label="Quand">{formatDate(selectedEntry.timestamp)}</Descriptions.Item>
              <Descriptions.Item label="Environnement">
                {selectedEntry.details?.environment?.toUpperCase() || '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Résultat">
                <Tag color={STATUS_CONFIG[selectedEntry.derived_status]?.color}>
                  {STATUS_CONFIG[selectedEntry.derived_status]?.label}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="Adresse IP">{selectedEntry.ip_address || '—'}</Descriptions.Item>
              <Descriptions.Item label="Correlation ID">
                <Text copyable={selectedEntry.correlation_id ? { text: selectedEntry.correlation_id } : undefined}>
                  {selectedEntry.correlation_id || '—'}
                </Text>
              </Descriptions.Item>
              {selectedEntry.details?.servicenow_change_id && (
                <Descriptions.Item label="Change ServiceNow">
                  <Text copyable={{ text: String(selectedEntry.details.servicenow_change_id) }}>
                    {String(selectedEntry.details.servicenow_change_id)}
                  </Text>
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* Parameters if available */}
            {selectedEntry.details?.parameters && (
              <Card title="Paramètres" size="small" style={{ marginBottom: 24 }}>
                <pre style={{ margin: 0, fontSize: 12, whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(selectedEntry.details.parameters, null, 2)}
                </pre>
              </Card>
            )}

            {/* Execution timeline if available */}
            {selectedExecution && selectedSteps.length > 0 && (
              <Card title="Timeline d'exécution" size="small">
                <ExecutionTimeline
                  execution={selectedExecution}
                  steps={selectedSteps}
                  mode="historical"
                />
              </Card>
            )}
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}
