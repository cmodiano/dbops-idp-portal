/**
 * IntegrationsTable — liste des intégrations (Story 2.28, AC2).
 * Colonnes : icône, nom, type, URL, date de création. Actions : Modifier, Supprimer (confirmation).
 */

import { Table, Button, Space, Modal, Avatar, Tag, Tooltip } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  ApiOutlined,
  CloudServerOutlined,
  BuildOutlined,
  BranchesOutlined,
  ProjectOutlined,
  GithubOutlined,
} from '@ant-design/icons';
import type { IntegrationListItem, IntegrationType } from '../../types/api';
import {
  INTEGRATION_TYPE_LABELS,
  INTEGRATION_TYPE_ICON_COLORS,
  INTEGRATION_TYPE_TAG_COLORS,
} from '../../types/api';

export interface IntegrationsTableProps {
  dataSource: IntegrationListItem[];
  loading?: boolean;
  onEdit: (record: IntegrationListItem) => void;
  onDelete: (record: IntegrationListItem) => Promise<void>;
  onNew: () => void;
  onRefresh?: () => void;
}

const TYPE_ICONS: Record<IntegrationType, React.ReactNode> = {
  aap: <ApiOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.aap }} />,
  servicenow: <CloudServerOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.servicenow }} />,
  terraform: <BuildOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.terraform }} />,
  azuredevops: <BranchesOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.azuredevops }} />,
  jira: <ProjectOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.jira }} />,
  github_actions: <GithubOutlined style={{ color: INTEGRATION_TYPE_ICON_COLORS.github_actions }} />,
};

function truncateUrl(url: string, max = 40): string {
  if (url.length <= max) return url;
  return `${url.slice(0, max)}…`;
}

function renderIcon(record: IntegrationListItem) {
  const icon = record.icon;
  if (icon && (icon.startsWith('http://') || icon.startsWith('https://'))) {
    return <Avatar src={icon} shape="square" size="small" />;
  }
  return (
    <span style={{ fontSize: 18 }} title={INTEGRATION_TYPE_LABELS[record.type]}>
      {TYPE_ICONS[record.type]}
    </span>
  );
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
      render: (t: IntegrationType) => (
        <Tag color={INTEGRATION_TYPE_TAG_COLORS[t]}>{INTEGRATION_TYPE_LABELS[t]}</Tag>
      ),
      sorter: (a, b) => a.type.localeCompare(b.type),
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
