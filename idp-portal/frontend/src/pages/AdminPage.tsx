/**
 * AdminPage - Administration du Catalogue (Story 2.1, AC #1).
 *
 * Features:
 * - List of existing actions (table)
 * - "Nouvelle action" button to open creation modal
 * - Success/error notifications
 */

import { useState, useEffect, useCallback } from 'react';
import { Typography, Button, Table, Space, Tag, notification } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { ActionForm } from '../components/admin/ActionForm';
import { createAction, getAction, listActions } from '../services/admin_service';
import type { ActionCreate, ActionResponse, ActionDetail, ActionStatus } from '../types/api';

const { Title } = Typography;

const STATUS_COLORS: Record<ActionStatus, string> = {
  draft: 'default',
  published: 'success',
  disabled: 'error',
};

const STATUS_LABELS: Record<ActionStatus, string> = {
  draft: 'Brouillon',
  published: 'Publie',
  disabled: 'Desactive',
};

const getColumns = (
  onEdit: (record: ActionResponse) => void,
): ColumnsType<ActionResponse> => [
  {
    title: 'Nom',
    dataIndex: 'name',
    key: 'name',
    sorter: (a, b) => a.name.localeCompare(b.name),
  },
  {
    title: 'Categorie',
    dataIndex: 'category',
    key: 'category',
    filters: [
      { text: 'Provisioning', value: 'Provisioning' },
      { text: 'Patching', value: 'Patching' },
      { text: 'Administration', value: 'Administration' },
      { text: 'Monitoring', value: 'Monitoring' },
    ],
    onFilter: (value, record) => record.category === value,
  },
  {
    title: 'Moteur',
    dataIndex: 'engine',
    key: 'engine',
  },
  {
    title: 'Plateforme',
    dataIndex: 'platform',
    key: 'platform',
  },
  {
    title: 'Statut',
    dataIndex: 'status',
    key: 'status',
    render: (status: ActionStatus) => (
      <Tag color={STATUS_COLORS[status]}>{STATUS_LABELS[status]}</Tag>
    ),
    filters: [
      { text: 'Brouillon', value: 'draft' },
      { text: 'Publie', value: 'published' },
      { text: 'Desactive', value: 'disabled' },
    ],
    onFilter: (value, record) => record.status === value,
  },
  {
    title: 'Date de creation',
    dataIndex: 'created_at',
    key: 'created_at',
    render: (date: string) => new Date(date).toLocaleDateString('fr-CA'),
    sorter: (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    defaultSortOrder: 'descend',
  },
  {
    title: '',
    key: 'actions',
    width: 100,
    render: (_: unknown, record: ActionResponse) =>
      record.status === 'draft' ? (
        <Button type="link" size="small" onClick={() => onEdit(record)}>
          Modifier
        </Button>
      ) : null,
  },
];

export default function AdminPage() {
  const [actions, setActions] = useState<ActionResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [editAction, setEditAction] = useState<ActionDetail | null>(null);

  const fetchActions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listActions();
      setActions(data);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement',
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  const handleCreate = async (action: ActionCreate) => {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createAction(action);
      return created;
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Erreur de création');
      setSubmitting(false);
      throw err;
    }
  };

  const handleEditSubmit = async (_action: ActionCreate) => {
    if (!editAction) throw new Error('editAction manquant');
    return editAction;
  };

  const handleEdit = async (record: ActionResponse) => {
    setSubmitError(null);
    try {
      const detail = await getAction(record.id);
      setEditAction(detail);
      setModalOpen(true);
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de charger l\'action',
      });
    }
  };

  const handleSuccess = (action: ActionDetail | ActionResponse) => {
    const wasEdit = !!editAction;
    setSubmitting(false);
    setModalOpen(false);
    setEditAction(null);
    setSubmitError(null);
    const name = 'name' in action ? action.name : '';
    notification.success({
      message: 'Succès',
      description: wasEdit ? `Action "${name}" mise à jour` : `Action "${name}" créée avec succès`,
    });
    fetchActions();
  };

  const handleCancel = () => {
    setModalOpen(false);
    setEditAction(null);
    setSubmitError(null);
  };

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={2} style={{ margin: 0 }}>
          Administration du Catalogue
        </Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchActions} loading={loading}>
            Actualiser
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditAction(null);
              setModalOpen(true);
            }}
          >
            Nouvelle action
          </Button>
        </Space>
      </Space>

      <Table
        columns={getColumns(handleEdit)}
        dataSource={actions}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10, showSizeChanger: true }}
        locale={{ emptyText: 'Aucune action dans le catalogue' }}
      />

      <ActionForm
        open={modalOpen}
        onCancel={handleCancel}
        onSubmit={editAction ? handleEditSubmit : handleCreate}
        loading={submitting}
        error={submitError}
        editAction={editAction}
        onSuccess={handleSuccess}
      />
    </div>
  );
}
