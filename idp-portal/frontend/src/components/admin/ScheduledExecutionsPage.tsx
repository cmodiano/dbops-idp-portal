/**
 * ScheduledExecutionsPage - Liste des exécutions planifiées (Story 11.6, 11.7).
 *
 * Features:
 * - Table avec colonnes : Type, Action, Utilisateur, Date/heure planifiée, Statut, Environnement, Date de création, Actions
 * - Filtrage par statut, action, plage de dates (AC7-AC9)
 * - RBAC : DBA voit ses propres exécutions, DBOPS voit toutes (AC2) - géré côté backend
 * - Indicateur visuel pour exécutions < 24h (AC4)
 * - Modal de confirmation d'annulation (AC5)
 * - Modal de détails avec info récurrence (AC10, Story 11.7 AC8)
 * - Activation/désactivation des récurrences (Story 11.7 AC9, AC10)
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
  Popconfirm,
} from 'antd';
import type { TableProps } from 'antd';
import { ClockCircleOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  listScheduledExecutions,
  cancelScheduledExecution,
  toggleRecurringPattern,
} from '../../services/scheduled_execution_service';
import { describeCronExpression } from '../../utils/cronHelper';
import type {
  ScheduledExecutionListItem,
  ScheduledExecutionFilters,
  ScheduledExecutionStatus,
  RecurringPatternResponse,
} from '../../types/api';

const { RangePicker } = DatePicker;

/** Check if a date is within the next 24 hours and in the future. */
function isWithin24Hours(scheduledAt: string | null): boolean {
  if (!scheduledAt) return false;
  const scheduledDate = dayjs(scheduledAt);
  const now = dayjs();
  return scheduledDate.isAfter(now) && scheduledDate.diff(now, 'hour') <= 24;
}

/** Day names for weekly pattern display (Story 11.7, AC7). */
const DAY_NAMES: Record<number, string> = {
  1: 'lundis',
  2: 'mardis',
  3: 'mercredis',
  4: 'jeudis',
  5: 'vendredis',
  6: 'samedis',
  7: 'dimanches',
};

/** Format recurring pattern display (Story 11.7 AC7, Story 11.8 AC8). */
function formatRecurrenceDisplay(recurringPattern: RecurringPatternResponse): string {
  const { pattern_type, pattern_config } = recurringPattern;

  // Story 11.8: Handle cron pattern (AC8)
  if (pattern_type === 'cron') {
    const cronExpression = 'cron_expression' in pattern_config ? pattern_config.cron_expression : '';
    if (cronExpression) {
      return describeCronExpression(cronExpression as string);
    }
    return 'Expression cron';
  }

  const hour = String('hour' in pattern_config ? pattern_config.hour : 0).padStart(2, '0');
  const minute = String('minute' in pattern_config ? pattern_config.minute : 0).padStart(2, '0');

  if (pattern_type === 'daily') {
    return `Tous les jours à ${hour}:${minute} (UTC)`;
  } else if (pattern_type === 'weekly') {
    const dayOfWeek = 'day_of_week' in pattern_config ? pattern_config.day_of_week : 1;
    const dayName = DAY_NAMES[dayOfWeek as number] || 'jours';
    return `Tous les ${dayName} à ${hour}:${minute} (UTC)`;
  }
  return '';
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

  // Story 11.7: Toggle recurring pattern state
  const [togglingPattern, setTogglingPattern] = useState(false);

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

  // Story 11.7: Handle toggle recurring pattern (AC9, AC10)
  const handleToggleRecurringPattern = async (newIsActive: boolean) => {
    if (!selectedExecution?.recurring_pattern) return;

    setTogglingPattern(true);
    try {
      await toggleRecurringPattern(
        selectedExecution.scheduled_execution_id,
        newIsActive
      );

      notification.success({
        message: newIsActive ? 'Récurrence réactivée' : 'Récurrence désactivée',
        description: newIsActive
          ? 'La récurrence a été réactivée avec succès'
          : 'La récurrence a été désactivée avec succès',
      });

      setDetailsModalVisible(false);
      setSelectedExecution(null);
      loadScheduledExecutions(pagination.current, pagination.pageSize);
    } catch (err: unknown) {
      const error = err as { status?: number; message?: string };
      if (error.status === 404) {
        notification.error({
          message: 'Erreur',
          description: 'Récurrence introuvable',
        });
      } else if (error.status === 403) {
        notification.error({
          message: 'Permission refusée',
          description: "Vous n'avez pas la permission de modifier cette récurrence",
        });
      } else {
        notification.error({
          message: 'Erreur',
          description: error.message ?? 'Une erreur est survenue',
        });
      }
    } finally {
      setTogglingPattern(false);
    }
  };

  const columns: TableProps<ScheduledExecutionListItem>['columns'] = [
    // Story 11.7, 11.8: Type column (AC7, AC12 - distinct badges for cron)
    {
      title: 'Type',
      key: 'type',
      width: 150,
      render: (_: unknown, record: ScheduledExecutionListItem) => {
        if (record.recurring_pattern) {
          // Story 11.8 AC7: Purple badge for cron patterns
          if (record.recurring_pattern.pattern_type === 'cron') {
            return (
              <Tag color="purple" icon={<SyncOutlined />}>
                Récurrent - Cron
              </Tag>
            );
          }
          // Story 11.7: Blue badge for daily/weekly patterns
          return (
            <Tag color="blue" icon={<SyncOutlined />}>
              Récurrent
            </Tag>
          );
        }
        return <Tag>Unique</Tag>;
      },
    },
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
      sorter: (a, b) => {
        const aDate = a.recurring_pattern?.next_execution_date ?? a.scheduled_at;
        const bDate = b.recurring_pattern?.next_execution_date ?? b.scheduled_at;
        return dayjs(aDate).unix() - dayjs(bDate).unix();
      },
      defaultSortOrder: 'ascend',
      render: (_: unknown, record: ScheduledExecutionListItem) => {
        // Story 11.7: Different display for recurring vs one-time
        if (record.recurring_pattern) {
          const recurrenceText = formatRecurrenceDisplay(record.recurring_pattern);
          const nextExecution = record.recurring_pattern.next_execution_date
            ? dayjs(record.recurring_pattern.next_execution_date)
            : null;
          const isActive = record.recurring_pattern.is_active;

          return (
            <div>
              <div style={{ color: isActive ? 'inherit' : '#999' }}>{recurrenceText}</div>
              {nextExecution && isActive && (
                <div style={{ fontSize: '12px', color: '#888' }}>
                  Prochaine : {nextExecution.format('DD/MM/YYYY à HH:mm')}
                  {isWithin24Hours(record.recurring_pattern.next_execution_date) && (
                    <Tag color="orange" style={{ marginLeft: 8 }}>
                      Bientôt
                    </Tag>
                  )}
                </div>
              )}
              {!isActive && (
                <div style={{ fontSize: '12px', color: '#ff4d4f' }}>
                  (Désactivé)
                </div>
              )}
            </div>
          );
        }

        // One-time execution
        const scheduledAt = record.scheduled_at;
        if (!scheduledAt) return '—';
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
          {record.status === 'pending' && !record.recurring_pattern && (
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
          // Story 11.7 AC9/AC10: Toggle buttons for recurring patterns
          ...(selectedExecution?.recurring_pattern
            ? [
                selectedExecution.recurring_pattern.is_active ? (
                  <Popconfirm
                    key="disable"
                    title="Désactiver la récurrence"
                    description="Êtes-vous sûr de vouloir désactiver cette récurrence ?"
                    onConfirm={() => handleToggleRecurringPattern(false)}
                    okText="Désactiver"
                    cancelText="Annuler"
                    okButtonProps={{ danger: true }}
                  >
                    <Button danger loading={togglingPattern}>
                      Désactiver la récurrence
                    </Button>
                  </Popconfirm>
                ) : (
                  <Button
                    key="enable"
                    type="primary"
                    loading={togglingPattern}
                    onClick={() => handleToggleRecurringPattern(true)}
                  >
                    Réactiver la récurrence
                  </Button>
                ),
              ]
            : []),
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
            {/* Story 11.7 AC8, Story 11.8 AC8: Type for recurring executions */}
            <Descriptions.Item label="Type">
              {selectedExecution.recurring_pattern ? (
                <Tag color="blue" icon={<SyncOutlined />}>
                  Récurrent - {
                    selectedExecution.recurring_pattern.pattern_type === 'daily' ? 'Daily' :
                    selectedExecution.recurring_pattern.pattern_type === 'weekly' ? 'Weekly' :
                    selectedExecution.recurring_pattern.pattern_type === 'cron' ? 'Cron' : 'Unknown'
                  }
                </Tag>
              ) : (
                <Tag>Unique</Tag>
              )}
            </Descriptions.Item>
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
            {/* Story 11.7 AC8, Story 11.8 AC8: Configuration for recurring patterns */}
            {selectedExecution.recurring_pattern ? (
              <>
                <Descriptions.Item label="Configuration">
                  {formatRecurrenceDisplay(selectedExecution.recurring_pattern)}
                  {/* Story 11.8: Show raw cron expression for cron patterns */}
                  {selectedExecution.recurring_pattern.pattern_type === 'cron' &&
                    'cron_expression' in selectedExecution.recurring_pattern.pattern_config && (
                    <div style={{ marginTop: 4, fontSize: 12, color: '#888' }}>
                      Expression : <code>{selectedExecution.recurring_pattern.pattern_config.cron_expression as string}</code>
                    </div>
                  )}
                </Descriptions.Item>
                <Descriptions.Item label="Prochaine exécution">
                  {selectedExecution.recurring_pattern.next_execution_date
                    ? dayjs(selectedExecution.recurring_pattern.next_execution_date).format('DD/MM/YYYY à HH:mm') + ' (UTC)'
                    : '—'}
                </Descriptions.Item>
                <Descriptions.Item label="Statut récurrence">
                  {selectedExecution.recurring_pattern.is_active ? (
                    <Badge status="success" text="Actif" />
                  ) : (
                    <Badge status="default" text="Désactivé" />
                  )}
                </Descriptions.Item>
              </>
            ) : (
              <Descriptions.Item label="Date/heure planifiée">
                {dayjs(selectedExecution.scheduled_at).format('DD/MM/YYYY à HH:mm')} (UTC)
              </Descriptions.Item>
            )}
            <Descriptions.Item label="Statut exécution">
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
