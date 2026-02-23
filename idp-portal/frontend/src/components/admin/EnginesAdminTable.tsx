/**
 * EnginesAdminTable — Admin table for REF_ENGINES (Story 31.10, AC1/AC2/AC3).
 * Pattern: CategoriesAdminTable.
 * Differences: no creation, no deletion (use deactivate), icon preview column.
 */

import { useState, useEffect, useCallback } from 'react';
import { Table, Button, Space, Tag, App, Avatar } from 'antd';
import type { TableProps } from 'antd';
import { ReloadOutlined, EditOutlined, StopOutlined, DatabaseOutlined } from '@ant-design/icons';
import type { RefEngine } from '../../services/reference_service';
import { fetchEnginesForAdmin, updateEngine } from '../../services/engines_service';
import { invalidateEngineIconCache } from '../../utils/engineIconCache';
import { invalidateEnginesCache } from '../../hooks/useEngines';
import { EngineForm } from './EngineForm';

export function EnginesAdminTable() {
  const { notification, modal } = App.useApp();
  const [engines, setEngines] = useState<RefEngine[]>([]);
  const [loading, setLoading] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editEngine, setEditEngine] = useState<RefEngine | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchEnginesForAdmin(false);
      setEngines(data);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement des moteurs',
      });
    } finally {
      setLoading(false);
    }
  }, [notification]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleEdit = (record: RefEngine) => {
    setEditEngine(record);
    setFormOpen(true);
  };

  const handleDeactivate = (record: RefEngine) => {
    modal.confirm({
      title: 'Désactiver le moteur',
      content: `Voulez-vous vraiment désactiver le moteur « ${record.label} » (${record.code}) ?`,
      okText: 'Désactiver',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await updateEngine(record.id, { is_active: 0 });
          notification.success({
            message: 'Succès',
            description: `Moteur « ${record.label} » désactivé`,
          });
          invalidateEngineIconCache();
          invalidateEnginesCache();
          fetchData();
        } catch (err) {
          notification.error({
            message: 'Erreur',
            description: err instanceof Error ? err.message : 'Impossible de désactiver le moteur',
          });
        }
      },
    });
  };

  const handleFormSuccess = () => {
    setFormOpen(false);
    setEditEngine(null);
    invalidateEngineIconCache();
    invalidateEnginesCache();
    fetchData();
  };

  const handleFormCancel = () => {
    setFormOpen(false);
    setEditEngine(null);
  };

  const columns: TableProps<RefEngine>['columns'] = [
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      sorter: (a, b) => a.code.localeCompare(b.code),
    },
    {
      title: 'Libellé',
      dataIndex: 'label',
      key: 'label',
      sorter: (a, b) => a.label.localeCompare(b.label),
    },
    {
      title: 'Icône',
      dataIndex: 'icon_url',
      key: 'icon_url',
      width: 80,
      render: (iconUrl: string | null) => (
        <Avatar
          src={iconUrl || undefined}
          size={24}
          shape="square"
          icon={<DatabaseOutlined />}
          alt="Icône moteur"
        />
      ),
    },
    {
      title: 'Ordre',
      dataIndex: 'display_order',
      key: 'display_order',
      width: 100,
      sorter: (a, b) => a.display_order - b.display_order,
      defaultSortOrder: 'ascend',
    },
    {
      title: 'Actif',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (val: number) => (
        <Tag color={val === 1 ? 'green' : 'default'}>
          {val === 1 ? 'Oui' : 'Non'}
        </Tag>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 200,
      render: (_: unknown, record: RefEngine) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            Modifier
          </Button>
          {record.is_active === 1 && (
            <Button type="link" size="small" danger icon={<StopOutlined />} onClick={() => handleDeactivate(record)}>
              Désactiver
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <Table<RefEngine>
        columns={columns}
        dataSource={engines}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: true }}
        locale={{ emptyText: 'Aucun moteur' }}
        title={() => (
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <span>Moteurs ({engines.length})</span>
            <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
              Actualiser
            </Button>
          </Space>
        )}
      />
      <EngineForm
        open={formOpen}
        onCancel={handleFormCancel}
        onSuccess={handleFormSuccess}
        editEngine={editEngine}
      />
    </>
  );
}
