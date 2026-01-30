/**
 * IntegrationsTable — liste des intégrations (Story 2.28, 4.9).
 * Story 4.9: Type libre (string), auth_flow, icône uploadée affichée.
 * Colonnes : icône, nom, type, URL, auth_flow, date de création. Actions : Modifier, Supprimer.
 */

import { Table, Button, Space, Modal, Avatar, Tag, Tooltip } from 'antd';
import { ReloadOutlined, ApiOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { IntegrationListItem } from '../../types/api';
import { AUTH_FLOW_LABELS } from '../../types/api';

export interface IntegrationsTableProps {
  dataSource: IntegrationListItem[];
  loading?: boolean;
  onEdit: (record: IntegrationListItem) => void;
  onDelete: (record: IntegrationListItem) => Promise<void>;
  onNew: () => void;
  onRefresh?: () => void;
}

function truncateUrl(url: string, max = 40): string {
  if (url.length <= max) return url;
  return `${url.slice(0, max)}…`;
}

/** Render icon: uploaded icon (/static/...), URL (http...), or fallback (Story 4.9 AC3). */
function renderIcon(record: IntegrationListItem) {
  const icon = record.icon;
  if (icon) {
    // Uploaded icon (starts with /) or external URL
    return <Avatar src={icon} shape="square" size="small" icon={<ApiOutlined />} />;
  }
  // Fallback: generic API icon
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
  const handleDeleteClick = (record: IntegrationListItem) => {
    Modal.confirm({
      title: 'Supprimer l\'intégration',
      content: `Voulez-vous vraiment supprimer l'intégration « ${record.name} » ?`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: () => onDelete(record),
    });
  };

  const columns: ColumnsType<IntegrationListItem> = [
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
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      render: (t: string) => <Tag>{t}</Tag>,
      sorter: (a, b) => a.type.localeCompare(b.type),
    },
    {
      title: 'Auth Flow',
      dataIndex: 'auth_flow',
      key: 'auth_flow',
      render: (flow: string | null) => (
        flow ? <Tag color="blue">{AUTH_FLOW_LABELS[flow as keyof typeof AUTH_FLOW_LABELS] || flow}</Tag> : '—'
      ),
    },
    {
      title: 'URL',
      dataIndex: 'base_url',
      key: 'base_url',
      ellipsis: true,
      render: (url: string) => truncateUrl(url),
      sorter: (a, b) => a.base_url.localeCompare(b.base_url),
    },
    {
      title: 'Date de création',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => new Date(d).toLocaleDateString('fr-CA'),
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: 'descend',
    },
    {
      title: '',
      key: 'actions',
      width: 180,
      render: (_: unknown, record: IntegrationListItem) => (
        <Space size="small">
          <Button type="link" size="small" onClick={() => onEdit(record)}>
            Modifier
          </Button>
          <Button type="link" size="small" danger onClick={() => handleDeleteClick(record)}>
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
      pagination={{ pageSize: 10, showSizeChanger: true }}
      locale={{ emptyText: 'Aucune intégration' }}
      title={() => (
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <span>Intégrations ({dataSource.length})</span>
          <Space>
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
