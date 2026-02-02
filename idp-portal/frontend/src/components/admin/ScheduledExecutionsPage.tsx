/**
 * ScheduledExecutionsPage - Liste des exécutions planifiées (Story 11.6).
 *
 * Features:
 * - Table avec colonnes : Action, Utilisateur, Date/heure planifiée, Statut, Environnement, Date de création, Actions
 * - Filtrage par statut, action, plage de dates (AC7-AC9)
 * - RBAC : DBA voit ses propres exécutions, DBOPS voit toutes (AC2) - géré côté backend
 * - Indicateur visuel pour exécutions < 24h (AC4)
 * - Modal de confirmation d'annulation (AC5)
 * - Modal de détails (AC10)
 */

import { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Badge,
  Tag,
  Button,
  Space,
  Select,
  Modal,
  Descriptions,
  App,
  DatePicker,
  Card,
} from 'antd';
import type { TableProps } from 'antd';
import { ClockCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  listScheduledExecutions,
  cancelScheduledExecution,
} from '../../services/scheduled_execution_service';
import type {
  ScheduledExecutionListItem,
  ScheduledExecutionFilters,
  ScheduledExecutionStatus,
} from '../../types/api';

const { RangePicker } = DatePicker;

/** Check if a date is within the next 24 hours and in the future. */
function isWithin24Hours(scheduledAt: string): boolean {
  const scheduledDate = dayjs(scheduledAt);
  const now = dayjs();
  return scheduledDate.isAfter(now) && scheduledDate.diff(now, 'hour') <= 24;
}

/** Badge status mapping for execution status. */
const STATUS_CONFIG: Record<
  ScheduledExecutionStatus,
  { status: 'processing' | 'success' | 'default'; text: string }
> = {
  pending: { status: 'processing', text: 'En attente' },
  executed: { status: 'success', text: 'Exécutée' },
  cancelled: { status: 'default', text: 'Annulée' },
};

/** Environment color mapping. */
const ENV_COLORS: Record<string, string> = {
  dev: 'blue',
  staging: 'orange',
  prod: 'red',
};

export default function ScheduledExecutionsPage() {
  const { notification } = App.useApp();
  const [scheduledExecutions, setScheduledExecutions] = useState<ScheduledExecutionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<ScheduledExecutionFilters>({});
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });

  // Cancel modal state
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<ScheduledExecutionListItem | null>(null);
  const [cancelLoading, setCancelLoading] = useState(false);

  // Details modal state
  const [detailsModalVisible, setDetailsModalVisible] = useState(false);

  const loadScheduledExecutions = useCallback(
    async (page = 1, pageSize = 10) => {
      setLoading(true);
      try {
        const offset = (page - 1) * pageSize;
        const response = await listScheduledExecutions(filters, pageSize, offset);
        setScheduledExecutions(response.data);
        setPagination({
          current: response.pagination.page,
          pageSize: response.pagination.page_size,
          total: response.pagination.total_count,
        });
      } catch (err) {
        notification.error({
          message: 'Erreur',
          description: err instanceof Error ? err.message : 'Impossible de charger les exécutions planifiées',
        });
      } finally {
        setLoading(false);
      }
    },
    [filters, notification]
  );

  useEffect(() => {
    loadScheduledExecutions(1, pagination.pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const handleTableChange: TableProps<ScheduledExecutionListItem>['onChange'] = (pag) => {
    loadScheduledExecutions(pag.current ?? 1, pag.pageSize ?? 10);
  };

  const handleShowCancelModal = (record: ScheduledExecutionListItem) => {
    setSelectedExecution(record);
    setCancelModalVisible(true);
  };

  const handleShowDetailsModal = (record: ScheduledExecutionListItem) => {
    setSelectedExecution(record);
    setDetailsModalVisible(true);
  };

  const handleCancelExecution = async () => {
    if (!selectedExecution) return;

    setCancelLoading(true);
    try {
      await cancelScheduledExecution(selectedExecution.scheduled_execution_id);
      notification.success({
        message: 'Annulation réussie',
        description: 'Exécution planifiée annulée avec succès',
      });
      setCancelModalVisible(false);
      setSelectedExecution(null);
      loadScheduledExecutions(pagination.current, pagination.pageSize);
    } catch (err: unknown) {
      const error = err as { status?: number; message?: string };
      if (error.status === 400) {
        notification.error({
          message: 'Erreur',
          description: 'Cette exécution ne peut pas être annulée (déjà exécutée ou annulée)',
        });
      } else if (error.status === 403) {
        notification.error({
          message: 'Permission refusée',
          description: "Vous n'avez pas la permission d'annuler cette exécution",
        });
      } else {
        notification.error({
          message: 'Erreur',
          description: error.message ?? "Une erreur est survenue lors de l'annulation",
        });
      }
    } finally {
      setCancelLoading(false);
    }
  };

  const handleFilterStatusChange = (value: ScheduledExecutionStatus | undefined) => {
    setFilters((prev) => ({ ...prev, status: value }));
  };

  const handleFilterDateRangeChange = (
    dates: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null
  ) => {
    if (dates && dates[0] && dates[1]) {
      setFilters((prev) => ({
        ...prev,
        scheduled_from: dates[0]!.startOf('day').toISOString(),
        scheduled_to: dates[1]!.endOf('day').toISOString(),
      }));
    } else {
      setFilters((prev) => ({
        ...prev,
        scheduled_from: undefined,
        scheduled_to: undefined,
      }));
    }
  };

  const columns: TableProps<ScheduledExecutionListItem>['columns'] = [
    {
      title: 'Action',
      dataIndex: 'action_name',
      key: 'action_name',
      sorter: (a, b) => a.action_name.localeCompare(b.action_name),
    },
    {
      title: 'Utilisateur',
      dataIndex: 'user_name',
      key: 'user_name',
      sorter: (a, b) => a.user_name.localeCompare(b.user_name),
    },
    {
      title: 'Date/heure planifiée',
      dataIndex: 'scheduled_at',
      key: 'scheduled_at',
      sorter: (a, b) => dayjs(a.scheduled_at).unix() - dayjs(b.scheduled_at).unix(),
      defaultSortOrder: 'ascend',
      render: (scheduledAt: string) => {
        const scheduledDate = dayjs(scheduledAt);
        const soon = isWithin24Hours(scheduledAt);
        return (
          <Space>
            <span>{scheduledDate.format('DD/MM/YYYY HH:mm')} (UTC)</span>
            {soon && (
              <Tag color="orange" icon={<ClockCircleOutlined />}>
                Bientôt
              </Tag>
            )}
          </Space>
        );
      },
    },
    {
      title: 'Statut',
      dataIndex: 'status',
      key: 'status',
      render: (status: ScheduledExecutionStatus) => {
        const config = STATUS_CONFIG[status];
        return <Badge status={config.status} text={config.text} />;
      },
    },
    {
      title: 'Environnement',
      dataIndex: 'environment',
      key: 'environment',
      render: (env: string) => <Tag color={ENV_COLORS[env] ?? 'default'}>{env}</Tag>,
    },
    {
      title: 'Date de création',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (createdAt: string) => dayjs(createdAt).format('DD/MM/YYYY'),
      sorter: (a, b) => dayjs(a.created_at).unix() - dayjs(b.created_at).unix(),
    },
    {
      title: '',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: ScheduledExecutionListItem) => (
        <Space size="small">
          {record.status === 'pending' && (
            <Button
              type="link"
              size="small"
              danger
              onClick={() => handleShowCancelModal(record)}
            >
              Annuler
            </Button>
          )}
          <Button
            type="link"
            size="small"
            onClick={() => handleShowDetailsModal(record)}
          >
            Voir détails
          </Button>
        </Space>
      ),
    },
  ];

  const rowClassName = (record: ScheduledExecutionListItem) => {
    return isWithin24Hours(record.scheduled_at) ? 'scheduled-soon' : '';
  };

  return (
    <>
      <Card
        title={
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <span>Exécutions planifiées ({pagination.total})</span>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => loadScheduledExecutions(pagination.current, pagination.pageSize)}
              loading={loading}
            >
              Actualiser
            </Button>
          </Space>
        }
        styles={{
          header: { borderBottom: 'none', paddingBottom: 0 },
          body: { paddingTop: 16 },
        }}
      >
        {/* Filters */}
        <Space style={{ marginBottom: 16 }} wrap>
          <Select
            placeholder="Filtrer par statut"
            style={{ width: 180 }}
            allowClear
            value={filters.status}
            onChange={handleFilterStatusChange}
            options={[
              { value: 'pending', label: 'En attente' },
              { value: 'executed', label: 'Exécutées' },
              { value: 'cancelled', label: 'Annulées' },
            ]}
          />
          {/* HIGH-3 FIX: AC8 requires filtering by action */}
          <Select
            placeholder="Filtrer par action"
            style={{ width: 220 }}
            allowClear
            showSearch
            value={filters.action_id}
            onChange={(value) => setFilters((prev) => ({ ...prev, action_id: value }))}
            options={Array.from(
              new Map(
                scheduledExecutions.map((se) => [se.action_id, se.action_name])
              ).entries()
            ).map(([id, name]) => ({ value: id, label: name }))}
            filterOption={(input, option) =>
              (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
            }
          />
          <RangePicker
            placeholder={['Date début', 'Date fin']}
            format="DD/MM/YYYY"
            onChange={handleFilterDateRangeChange}
          />
        </Space>

        {/* Table */}
        <Table
          columns={columns}
          dataSource={scheduledExecutions}
          rowKey="scheduled_execution_id"
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
          }}
          onChange={handleTableChange}
          rowClassName={rowClassName}
          locale={{ emptyText: 'Aucune exécution planifiée' }}
        />
      </Card>

      {/* Cancel Confirmation Modal */}
      <Modal
        title="Confirmer l'annulation"
        open={cancelModalVisible}
        onOk={handleCancelExecution}
        onCancel={() => {
          setCancelModalVisible(false);
          setSelectedExecution(null);
        }}
        okText="Confirmer l'annulation"
        cancelText="Annuler"
        okButtonProps={{ danger: true, loading: cancelLoading }}
        confirmLoading={cancelLoading}
      >
        <p>Êtes-vous sûr de vouloir annuler cette exécution planifiée ?</p>
        {selectedExecution && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="Action">{selectedExecution.action_name}</Descriptions.Item>
            <Descriptions.Item label="Planifiée pour">
              {dayjs(selectedExecution.scheduled_at).format('DD/MM/YYYY à HH:mm')} (UTC)
            </Descriptions.Item>
            <Descriptions.Item label="Utilisateur">{selectedExecution.user_name}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>

      {/* Details Modal */}
      <Modal
        title="Détails de l'exécution planifiée"
        open={detailsModalVisible}
        onCancel={() => {
          setDetailsModalVisible(false);
          setSelectedExecution(null);
        }}
        footer={[
          <Button
            key="close"
            onClick={() => {
              setDetailsModalVisible(false);
              setSelectedExecution(null);
            }}
          >
            Fermer
          </Button>,
        ]}
        width={700}
      >
        {selectedExecution && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="ID">{selectedExecution.scheduled_execution_id}</Descriptions.Item>
            <Descriptions.Item label="Action">
              {selectedExecution.action_name} (ID: {selectedExecution.action_id})
            </Descriptions.Item>
            <Descriptions.Item label="Utilisateur">
              {selectedExecution.user_name} (ID: {selectedExecution.user_id})
            </Descriptions.Item>
            <Descriptions.Item label="Environnement">
              <Tag color={ENV_COLORS[selectedExecution.environment] ?? 'default'}>
                {selectedExecution.environment}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Paramètres">
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {selectedExecution.parameters
                  ? JSON.stringify(selectedExecution.parameters, null, 2)
                  : '—'}
              </pre>
            </Descriptions.Item>
            <Descriptions.Item label="Date/heure planifiée">
              {dayjs(selectedExecution.scheduled_at).format('DD/MM/YYYY à HH:mm')} (UTC)
            </Descriptions.Item>
            <Descriptions.Item label="Statut">
              <Badge
                status={STATUS_CONFIG[selectedExecution.status].status}
                text={STATUS_CONFIG[selectedExecution.status].text}
              />
            </Descriptions.Item>
            <Descriptions.Item label="Date de création">
              {dayjs(selectedExecution.created_at).format('DD/MM/YYYY à HH:mm')}
            </Descriptions.Item>
            {/* HIGH-1 FIX: AC10 requires displaying correlation_id */}
            <Descriptions.Item label="Correlation ID">
              {selectedExecution.correlation_id ?? '—'}
            </Descriptions.Item>
            {/* HIGH-2 FIX: AC10 requires link to effective execution if status=executed */}
            {selectedExecution.status === 'executed' && selectedExecution.execution_id && (
              <Descriptions.Item label="Exécution effective">
                <a href={`/executions/${selectedExecution.execution_id}`}>
                  Voir l'exécution #{selectedExecution.execution_id}
                </a>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>

      {/* CSS for row highlighting */}
      <style>{`
        .scheduled-soon {
          background-color: rgba(250, 173, 20, 0.1) !important;
        }
        /* MEDIUM-1 FIX: Improve hover state for scheduled-soon rows */
        .scheduled-soon:hover td {
          background-color: rgba(250, 173, 20, 0.18) !important;
        }
      `}</style>
    </>
  );
}
