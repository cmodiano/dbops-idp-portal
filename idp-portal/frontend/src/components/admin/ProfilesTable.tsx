/**
 * ProfilesTable — list profiles (Story 2.9, AC #3).
 * Columns: nom, groupe AD, nombre de permissions, date de création. Actions: modifier, supprimer (confirmation).
 */

import { Table, Button, Space, App } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import type { TableProps } from 'antd';
import type { ProfileListItem } from '../../types/api';
import { formatLocalDate } from '../../utils/dateFormat';

export interface ProfilesTableProps {
  dataSource: ProfileListItem[];
  loading?: boolean;
  onEdit: (record: ProfileListItem) => void;
  onDelete: (record: ProfileListItem) => Promise<void>;
  onNew: () => void;
  /** Story 2.13: Export YAML (AC1). */
  onExportYaml?: () => void | Promise<void>;
  /** Story 2.13: Import YAML (AC2). */
  onImportYaml?: () => void;
}

export function ProfilesTable({ dataSource, loading, onEdit, onDelete, onNew, onExportYaml, onImportYaml }: ProfilesTableProps) {
  const { modal } = App.useApp();
  const handleDeleteClick = (record: ProfileListItem) => {
    modal.confirm({
      title: 'Supprimer le profil',
      content: `Voulez-vous vraiment supprimer le profil « ${record.name} » ?`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: () => onDelete(record),
    });
  };

  const columns: TableProps<ProfileListItem>['columns'] = [
    { title: 'Nom', dataIndex: 'name', key: 'name', sorter: (a, b) => a.name.localeCompare(b.name) },
    { title: 'Groupe AD', dataIndex: 'ad_group', key: 'ad_group' },
    {
      title: 'Admin',
      dataIndex: 'is_admin',
      key: 'is_admin',
      width: 80,
      align: 'center',
      sorter: (a, b) => Number(a.is_admin) - Number(b.is_admin),
      render: (v: boolean) => (v ? 'Oui' : 'Non'),
    },
    {
      title: 'Auditeur',
      dataIndex: 'is_auditor',
      key: 'is_auditor',
      width: 90,
      align: 'center',
      sorter: (a, b) => Number(a.is_auditor) - Number(b.is_auditor),
      render: (v: boolean) => (v ? 'Oui' : 'Non'),
    },
    {
      title: 'Permissions',
      dataIndex: 'permission_count',
      key: 'permission_count',
      width: 120,
      sorter: (a, b) => (a.permission_count ?? 0) - (b.permission_count ?? 0),
      render: (n: number) => (n != null ? n : 0),
    },
    {
      title: 'Date de création',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (d: string) => formatLocalDate(d),
      sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      defaultSortOrder: 'descend',
    },
    {
      title: '',
      key: 'actions',
      width: 280,
      render: (_: unknown, record: ProfileListItem) => (
        <Space size="small" style={{ whiteSpace: 'nowrap' }}>
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
    <Table
      columns={columns}
      dataSource={dataSource}
      rowKey="id"
      loading={loading}
      pagination={{ pageSize: 10, showSizeChanger: true }}
      locale={{ emptyText: 'Aucun profil' }}
      title={() => (
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <span>Profils ({dataSource.length})</span>
          <Space>
            {onExportYaml != null && (
              <Button onClick={onExportYaml}>Exporter YAML</Button>
            )}
            {onImportYaml != null && (
              <Button onClick={onImportYaml}>Importer YAML</Button>
            )}
            <Button type="primary" onClick={onNew}>
              Nouveau profil
            </Button>
          </Space>
        </Space>
      )}
    />
  );
}
