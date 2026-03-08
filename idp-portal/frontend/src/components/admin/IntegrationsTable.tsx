/**
 * IntegrationsTable — liste des intégrations (Story 2.28, 4.9, 24.3).
 * Story 24.3: Colonne Statut (badges colorés), filtre par statut, bouton Re-valider par ligne, bouton Re-valider tout.
 */

import { Table, Button, Space, Avatar, Tag, Tooltip, App } from 'antd';
import type { TableProps } from 'antd';
import { ReloadOutlined, ApiOutlined, EditOutlined, DeleteOutlined, SyncOutlined } from '@ant-design/icons';
import type { IntegrationListItem, IntegrationStatusType, HealthStatus } from '../../types/api';
import { AUTH_FLOW_LABELS } from '../../types/api';
import { DriftBadge } from './DriftBadge';
import { getIconUrl } from '../../utils/iconUrl';
import { HEALTH_CONFIG } from '../../utils/healthConfig';
import { useIntegrationValidation } from '../../hooks/useIntegrationValidation';
import { formatLocalDate, formatLocalDateTime } from '../../utils/dateFormat';

// Statut intégration (admin) — domaine distinct, config locale justifiée (SOLID-FE-10, Story 48.5 2026-02-26).
// Clés = IntegrationStatusType (valid/invalid/deprecated) ≠ statuts d'exécution (SUBMITTED/RUNNING/COMPLETED…).
// Format { color, text } différent de { color: BadgeStatusType, label } dans execution-status.ts.
// Seul consommateur = IntegrationsTable → extraction vers utils/integration-status.ts non justifiée.
/** Story 24.3: Status badge configuration. */
const STATUS_CONFIG: Record<string, { color: string; text: string }> = {
  valid: { color: 'success', text: 'Valide' },
  invalid: { color: 'error', text: 'Invalide' },
  deprecated: { color: 'warning', text: 'Déprécié' },
};

function buildHealthTooltip(record: IntegrationListItem): string {
  if (!record.health_checked_at) return 'Jamais vérifié';
  const date = formatLocalDateTime(record.health_checked_at);
  const base = `Dernière vérification : ${date}`;
  return record.health_error_message ? `${base}\nErreur : ${record.health_error_message}` : base;
}

export interface IntegrationsTableProps {
  dataSource: IntegrationListItem[];
  loading?: boolean;
  onEdit: (record: IntegrationListItem) => void;
  onDelete: (record: IntegrationListItem) => Promise<void>;
  onNew: () => void;
  onRefresh?: () => void;
}

/** Render icon: uploaded icon (/static/...), URL (http...), or fallback (Story 4.9 AC3). */
function renderIcon(record: IntegrationListItem) {
  const iconSrc = getIconUrl(record.icon);
  if (iconSrc) {
    return <Avatar src={iconSrc} shape="square" size="small" icon={<ApiOutlined />} />;
  }
  return <Avatar shape="square" size="small" icon={<ApiOutlined />} />;
}

export function IntegrationsTable({
  dataSource,
  loading,
  onEdit,
  onDelete,
  onNew,
  onRefresh,
}: IntegrationsTableProps) {
  const { modal, message, notification } = App.useApp();
  const { validateOne, validateAll: validateAllHook, validatingId, validatingAll } = useIntegrationValidation();

  const handleValidate = async (record: IntegrationListItem) => {
    try {
      const result = await validateOne(record.id);
      const config = STATUS_CONFIG[result.current_status] ?? STATUS_CONFIG.invalid;
      if (result.current_status === 'valid') {
        message.success(`Intégration validée avec succès. Statut : ${config.text}`);
      } else if (result.current_status === 'deprecated') {
        message.warning('Intégration dépréciée. Veuillez migrer vers un type supporté.');
      } else {
        message.error('Intégration invalide. Type non trouvé dans le catalogue.');
      }
      onRefresh?.();
    } catch {
      message.error('Erreur lors de la validation');
    }
  };

  const handleValidateAll = async () => {
    try {
      const stats = await validateAllHook();
      modal.info({
        title: 'Rapport de validation',
        content: (
          <div>
            <p><Tag color="success">Valide</Tag> {stats.valid}</p>
            <p><Tag color="error">Invalide</Tag> {stats.invalid}</p>
            <p><Tag color="warning">Déprécié</Tag> {stats.deprecated}</p>
            <p><strong>Mis à jour :</strong> {stats.updated} intégrations</p>
          </div>
        ),
      });
      onRefresh?.();
    } catch {
      notification.error({ message: 'Erreur', description: 'Erreur lors de la validation batch' });
    }
  };

  const handleDeleteClick = (record: IntegrationListItem) => {
    modal.confirm({
      title: 'Supprimer l\'intégration',
      content: `Voulez-vous vraiment supprimer l'intégration « ${record.name} » ?`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: () => onDelete(record),
    });
  };

  const columns: TableProps<IntegrationListItem>['columns'] = [
    {
      title: 'Icône',
      dataIndex: 'icon',
      key: 'icon',
      width: 72,
      render: (_: unknown, record: IntegrationListItem) => renderIcon(record),
    },
    {
      title: 'Nom',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 120,
      render: (t: string) => <Tag>{t}</Tag>,
      sorter: (a, b) => a.type.localeCompare(b.type),
    },
    {
      title: 'Statut',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      filters: [
        { text: 'Valide', value: 'valid' },
        { text: 'Invalide', value: 'invalid' },
        { text: 'Déprécié', value: 'deprecated' },
      ],
      onFilter: (value, record) => record.status === value,
      render: (status: IntegrationStatusType | undefined) => {
        const config = STATUS_CONFIG[status ?? 'valid'] ?? STATUS_CONFIG.valid;
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: 'Santé',
      key: 'health_status',
      width: 110,
      render: (_: unknown, record: IntegrationListItem) => {
        const status: HealthStatus = record.health_status ?? 'unknown';
        const cfg = HEALTH_CONFIG[status];
        return (
          <Tooltip title={buildHealthTooltip(record)}>
            <Tag color={cfg.color} aria-label={cfg.ariaLabel}>
              {cfg.text}
            </Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Sync Git',
      dataIndex: 'last_synced_at',
      key: 'drift',
      width: 120,
      render: (_: unknown, record: IntegrationListItem) => (
        <DriftBadge last_synced_at={record.last_synced_at} updated_at={record.updated_at} />
      ),
    },
    {
      title: 'Auth Flow',
      dataIndex: 'auth_flow',
      key: 'auth_flow',
      width: 200,
      ellipsis: { showTitle: false },
      render: (flow: string | null) => {
        const label = flow ? (AUTH_FLOW_LABELS[flow as keyof typeof AUTH_FLOW_LABELS] || flow) : null;
        return label ? (
          <Tooltip title={label}>
            <Tag color="blue" style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {label}
            </Tag>
          </Tooltip>
        ) : '—';
      },
    },
    {
      title: 'URL',
      dataIndex: 'base_url',
      key: 'base_url',
      width: 240,
      ellipsis: { showTitle: false },
      render: (url: string) => (
        <Tooltip title={url}>
          <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {url}
          </span>
        </Tooltip>
      ),
      sorter: (a, b) => a.base_url.localeCompare(b.base_url),
    },
    {
      title: () => <span style={{ whiteSpace: 'nowrap' }}>Date de création</span>,
      dataIndex: 'created_at',
      key: 'created_at',
      width: 130,
      render: (d: string) => formatLocalDate(d),
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: 'descend',
    },
    {
      title: '',
      key: 'actions',
      width: 320,
      render: (_: unknown, record: IntegrationListItem) => (
        <Space size="small" style={{ whiteSpace: 'nowrap' }}>
          <Tooltip title="Re-valider">
            <Button
              type="link"
              size="small"
              icon={<SyncOutlined spin={validatingId === record.id} />}
              loading={validatingId === record.id}
              onClick={() => handleValidate(record)}
            >
              Re-valider
            </Button>
          </Tooltip>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => onEdit(record)}>
            Modifier
          </Button>
          <Button
            type="link"
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteClick(record)}
          >
            Supprimer
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Table<IntegrationListItem>
      columns={columns}
      dataSource={dataSource}
      rowKey="id"
      loading={loading}
      scroll={{ x: 'max-content' }}
      pagination={{ pageSize: 10, showSizeChanger: true }}
      locale={{ emptyText: 'Aucune intégration' }}
      title={() => (
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <span>Intégrations ({dataSource.length})</span>
          <Space>
            <Tooltip title="Re-valider toutes les intégrations">
              <Button
                icon={<SyncOutlined />}
                onClick={handleValidateAll}
                loading={validatingAll}
              >
                Re-valider tout
              </Button>
            </Tooltip>
            {onRefresh && (
              <Tooltip title="Actualiser">
                <Button icon={<ReloadOutlined />} onClick={onRefresh} loading={loading}>
                  Actualiser
                </Button>
              </Tooltip>
            )}
            <Button type="primary" onClick={onNew}>
              Nouvelle intégration
            </Button>
          </Space>
        </Space>
      )}
    />
  );
}
