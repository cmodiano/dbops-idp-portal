/**
 * CategoriesAdminTable — Admin CRUD table for categories (Story 2.30, AC4/AC5).
 * Pattern: IntegrationsTable.
 */

import { useState, useEffect, useCallback } from 'react';
import { Table, Button, Space, Tag, Switch, App } from 'antd';
import type { TableProps } from 'antd';
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import type { RefCategory } from '../../types/api';
import { getCategories, deleteCategory } from '../../services/categories_service';
import { CategoryForm } from './CategoryForm';

export function CategoriesAdminTable() {
  const { notification, modal } = App.useApp();
  const [categories, setCategories] = useState<RefCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editCategory, setEditCategory] = useState<RefCategory | null>(null);

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getCategories(false); // Include inactive
      setCategories(data);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement des catégories',
      });
    } finally {
      setLoading(false);
    }
  }, [notification]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const handleEdit = (record: RefCategory) => {
    setEditCategory(record);
    setFormOpen(true);
  };

  const handleDelete = (record: RefCategory) => {
    modal.confirm({
      title: 'Désactiver la catégorie',
      content: `Voulez-vous vraiment désactiver la catégorie « ${record.label} » (${record.code}) ? Les actions ayant cette catégorie resteront associées.`,
      okText: 'Désactiver',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await deleteCategory(record.id);
          notification.success({
            message: 'Succès',
            description: `Catégorie « ${record.label} » désactivée`,
          });
          fetchCategories();
        } catch (err) {
          notification.error({
            message: 'Erreur',
            description: err instanceof Error ? err.message : 'Impossible de désactiver la catégorie',
          });
        }
      },
    });
  };

  const handleFormSuccess = () => {
    setFormOpen(false);
    setEditCategory(null);
    fetchCategories();
  };

  const handleFormCancel = () => {
    setFormOpen(false);
    setEditCategory(null);
  };

  const columns: TableProps<RefCategory>['columns'] = [
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
      render: (_: unknown, record: RefCategory) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            Modifier
          </Button>
          {record.is_active === 1 && (
            <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record)}>
              Désactiver
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <Table<RefCategory>
        columns={columns}
        dataSource={categories}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: true }}
        locale={{ emptyText: 'Aucune catégorie' }}
        title={() => (
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <span>Catégories ({categories.length})</span>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchCategories} loading={loading}>
                Actualiser
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditCategory(null);
                  setFormOpen(true);
                }}
              >
                Nouvelle catégorie
              </Button>
            </Space>
          </Space>
        )}
      />
      <CategoryForm
        open={formOpen}
        onCancel={handleFormCancel}
        onSuccess={handleFormSuccess}
        editCategory={editCategory}
      />
    </>
  );
}
