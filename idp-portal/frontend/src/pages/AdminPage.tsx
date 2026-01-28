/**
 * AdminPage - Administration du Catalogue (Story 2.1, AC #1; Story 2.4, AC #2).
 *
 * Features:
 * - List of existing actions (table) with execution count
 * - "Nouvelle action" button to open creation modal
 * - Success/error notifications
 * - Status badge with visual indicators
 */

import { useState, useEffect, useCallback } from 'react';
import { Typography, Button, Table, Space, notification } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { ActionForm } from '../components/admin/ActionForm';
import { ActionStatusBadge } from '../components/admin/ActionStatusBadge';
import { createAction, getAction, getAdminActions, updateActionStatus } from '../services/admin_service';
import type { ActionCreate, ActionListItem, ActionDetail, ActionStatus, StatusTransition, AdminActionsFilters } from '../types/api';

const { Title } = Typography;

const getColumns = (
  onEdit: (record: ActionListItem) => void,
  onStatusChange: (record: ActionListItem, transition: StatusTransition) => void,
): ColumnsType<ActionListItem> => [
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
    title: 'Statut',
    dataIndex: 'status',
    key: 'status',
    render: (status: ActionStatus) => <ActionStatusBadge status={status} />,
    filters: [
      { text: 'Brouillon', value: 'draft' },
      { text: 'Publiee', value: 'published' },
      { text: 'Desactivee', value: 'disabled' },
    ],
    onFilter: (value, record) => record.status === value,
  },
  {
    title: 'Executions',
    dataIndex: 'execution_count',
    key: 'execution_count',
    sorter: (a, b) => a.execution_count - b.execution_count,
    width: 100,
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
    width: 200,
    render: (_: unknown, record: ActionListItem) => (
      <Space size="small">
        {record.status === 'draft' && (
          <>
            <Button type="link" size="small" onClick={() => onEdit(record)}>
              Modifier
            </Button>
            <Button type="link" size="small" onClick={() => onStatusChange(record, 'publish')}>
              Publier
            </Button>
          </>
        )}
        {record.status === 'published' && (
          <>
            <Button type="link" size="small" onClick={() => onEdit(record)}>
              Voir
            </Button>
            <Button type="link" size="small" danger onClick={() => onStatusChange(record, 'disable')}>
              Desactiver
            </Button>
          </>
        )}
        {record.status === 'disabled' && (
          <>
            <Button type="link" size="small" onClick={() => onEdit(record)}>
              Voir
            </Button>
            <Button type="link" size="small" onClick={() => onStatusChange(record, 'enable')}>
              Reactiver
            </Button>
          </>
        )}
      </Space>
    ),
  },
];

export default function AdminPage() {
  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [editAction, setEditAction] = useState<ActionDetail | null>(null);

  const fetchActions = useCallback(async (filters?: AdminActionsFilters) => {
    setLoading(true);
    try {
      const response = await getAdminActions(filters);
      setActions(response.data);
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
      setSubmitError(err instanceof Error ? err.message : 'Erreur de creation');
      setSubmitting(false);
      throw err;
    }
  };

  const handleEditSubmit = async (_action: ActionCreate) => {
    if (!editAction) throw new Error('editAction manquant');
    return editAction;
  };

  const handleEdit = async (record: ActionListItem) => {
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

  const handleStatusChange = async (record: ActionListItem, transition: StatusTransition) => {
    try {
      await updateActionStatus(record.id, transition);
      const statusLabels: Record<StatusTransition, string> = {
        publish: 'publiee',
        disable: 'desactivee',
        enable: 'reactivee',
      };
      notification.success({
        message: 'Succes',
        description: `Action "${record.name}" ${statusLabels[transition]}`,
      });
      fetchActions();
    } catch (err) {
      notification.error({
        message: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de changer le statut',
      });
    }
  };

  const handleSuccess = (action: ActionDetail | ActionListItem) => {
    const wasEdit = !!editAction;
    setSubmitting(false);
    setModalOpen(false);
    setEditAction(null);
    setSubmitError(null);
    const name = 'name' in action ? action.name : '';
    notification.success({
      message: 'Succes',
      description: wasEdit ? `Action "${name}" mise a jour` : `Action "${name}" creee avec succes`,
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
        columns={getColumns(handleEdit, handleStatusChange)}
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
