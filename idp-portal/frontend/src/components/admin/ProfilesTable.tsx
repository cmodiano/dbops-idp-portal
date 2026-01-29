/**
 * ProfilesTable — list profiles (Story 2.9, AC #3).
 * Columns: nom, groupe AD, nombre de permissions, date de création. Actions: modifier, supprimer (confirmation).
 */

import { Table, Button, Space, Modal } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { ProfileListItem } from '../../types/api';

export interface ProfilesTableProps {
  dataSource: ProfileListItem[];
  loading?: boolean;
  onEdit: (record: ProfileListItem) => void;
  onDelete: (record: ProfileListItem) => Promise<void>;
  onNew: () => void;
}

export function ProfilesTable({ dataSource, loading, onEdit, onDelete, onNew }: ProfilesTableProps) {
  const handleDeleteClick = (record: ProfileListItem) => {
    Modal.confirm({
      title: 'Supprimer le profil',
      content: `Voulez-vous vraiment supprimer le profil « ${record.name} » ?`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: () => onDelete(record),
    });
  };

  const columns: ColumnsType<ProfileListItem> = [
    { title: 'Nom', dataIndex: 'name', key: 'name', sorter: (a, b) => a.name.localeCompare(b.name) },
    { title: 'Groupe AD', dataIndex: 'ad_group', key: 'ad_group' },
    {
      title: 'Permissions',
      dataIndex: 'permission_count',
      key: 'permission_count',
      width: 120,
      sorter: (a, b) => a.permission_count - b.permission_count,
      render: (n: number) => (n != null ? n : 0),
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
      render: (_: unknown, record: ProfileListItem) => (
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
          <Button type="primary" onClick={onNew}>
            Nouveau profil
          </Button>
        </Space>
      )}
    />
  );
}
