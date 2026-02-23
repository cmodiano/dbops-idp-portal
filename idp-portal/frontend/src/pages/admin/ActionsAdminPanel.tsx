import { useState, useEffect, useCallback } from 'react';
import { Typography, Button, Table, Space, Card, Tag, Checkbox, Modal, Input, App } from 'antd';

type NotificationInstance = ReturnType<typeof App.useApp>['notification'];
type ModalHookAPI = ReturnType<typeof App.useApp>['modal'];
import {
  PlusOutlined,
  ReloadOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';
import { ActionWizard } from '../../components/admin/ActionWizard';
import { createAction, getAction, getAdminActions, updateAction, updateActionStatus, deleteAction, deactivateAction, reactivateAction } from '../../services/admin_service';
import type { DeactivateConfirmation } from '../../services/admin_service';
import type { ActionCreate, ActionListItem, ActionDetail, ActionResponse, StatusTransition, AdminActionsFilters } from '../../types/api';
import { getActionsColumns } from './actionsColumns';

export interface ActionsAdminPanelProps {
  notification: NotificationInstance;
  modal: ModalHookAPI;
  isDark: boolean;
}

export function ActionsAdminPanel({ notification, modal, isDark }: ActionsAdminPanelProps) {
  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [editAction, setEditAction] = useState<ActionDetail | null>(null);
  const [wizardInitialItemType, setWizardInitialItemType] = useState<'action' | 'workflow' | null>(null);

  const [includeDisabled, setIncludeDisabled] = useState(false);
  const [cascadeModalOpen, setCascadeModalOpen] = useState(false);
  const [cascadeAction, setCascadeAction] = useState<ActionListItem | null>(null);
  const [cascadeWorkflows, setCascadeWorkflows] = useState<{ id: number; name: string; status: string }[]>([]);
  const [cascadeReason, setCascadeReason] = useState<string>('');

  const fetchActions = useCallback(async (filters?: AdminActionsFilters) => {
    setLoading(true);
    try {
      const mergedFilters: AdminActionsFilters = { ...filters };
      if (includeDisabled) mergedFilters.include_disabled = true;
      const response = await getAdminActions(mergedFilters);
      setActions(response.data ?? []);
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Erreur de chargement',
      });
    } finally {
      setLoading(false);
    }
  }, [notification, includeDisabled]);

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

  const handleEditSubmit = async (action: ActionCreate) => {
    if (!editAction) throw new Error('editAction manquant');
    const updated = await updateAction(editAction.id, action);
    return updated;
  };

  const handleEdit = async (record: ActionListItem) => {
    setSubmitError(null);
    try {
      const detail = await getAction(record.id);
      setEditAction(detail);
      setModalOpen(true);
    } catch (err) {
      notification.error({
        title: 'Erreur',
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
      const label = Object.hasOwn(statusLabels, transition) ? statusLabels[transition] : transition;
      notification.success({
        title: 'Succes',
        description: `Action "${record.name}" ${label}`,
      });
      fetchActions();
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de changer le statut',
      });
    }
  };

  const handleDelete = (record: ActionListItem) => {
    modal.confirm({
      title: 'Supprimer l\'action',
      content: `Voulez-vous vraiment supprimer definitivement l'action « ${record.name} » ? Cette operation est irreversible.`,
      okText: 'Supprimer',
      okType: 'danger',
      cancelText: 'Annuler',
      onOk: async () => {
        try {
          await deleteAction(record.id);
          notification.success({
            title: 'Succes',
            description: `Action « ${record.name} » supprimee`,
          });
          fetchActions();
        } catch (err) {
          notification.error({
            title: 'Erreur',
            description: err instanceof Error ? err.message : 'Impossible de supprimer l\'action',
          });
        }
      },
    });
  };

  const handleDeactivate = async (record: ActionListItem) => {
    try {
      const result = await deactivateAction(record.id);
      if ('status' in result && result.status === 'requires_confirmation') {
        const confirmation = result as DeactivateConfirmation;
        setCascadeAction(record);
        setCascadeWorkflows(confirmation.affected_workflows);
        setCascadeReason('');
        setCascadeModalOpen(true);
      } else {
        notification.success({
          title: 'Succes',
          description: `Action « ${record.name} » desactivee`,
        });
        fetchActions();
      }
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de desactiver l\'action',
      });
    }
  };

  const handleCascadeConfirm = async () => {
    if (!cascadeAction) return;
    try {
      await deactivateAction(cascadeAction.id, cascadeReason || undefined, true);
      notification.success({
        title: 'Succes',
        description: `Action « ${cascadeAction.name} » et ${cascadeWorkflows.length} workflow(s) desactive(s)`,
      });
      setCascadeModalOpen(false);
      setCascadeAction(null);
      setCascadeWorkflows([]);
      setCascadeReason('');
      fetchActions();
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de desactiver l\'action',
      });
    }
  };

  const handleReactivate = async (record: ActionListItem) => {
    try {
      await reactivateAction(record.id);
      notification.success({
        title: 'Succes',
        description: `Action « ${record.name} » reactivee`,
      });
      fetchActions();
    } catch (err) {
      notification.error({
        title: 'Erreur',
        description: err instanceof Error ? err.message : 'Impossible de reactiver l\'action',
      });
    }
  };

  const handleSuccess = (action: ActionDetail | ActionResponse | ActionListItem) => {
    const wasEdit = !!editAction;
    setSubmitting(false);
    setModalOpen(false);
    setEditAction(null);
    setWizardInitialItemType(null);
    setSubmitError(null);
    const name = 'name' in action ? action.name : '';
    notification.success({
      title: 'Succes',
      description: wasEdit ? `Action "${name}" mise a jour` : `Action "${name}" creee avec succes`,
    });
    fetchActions();
  };

  const handleCancel = () => {
    setModalOpen(false);
    setEditAction(null);
    setWizardInitialItemType(null);
    setSubmitError(null);
  };

  return (
    <>
      <Card
        title={
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <span>Actions ({actions.length})</span>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => fetchActions()} loading={loading}>
                Actualiser
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  setEditAction(null);
                  setWizardInitialItemType('action');
                  setModalOpen(true);
                }}
              >
                Nouvelle action
              </Button>
              <Button
                icon={<ApartmentOutlined />}
                onClick={() => {
                  setEditAction(null);
                  setWizardInitialItemType('workflow');
                  setModalOpen(true);
                }}
              >
                Nouveau workflow
              </Button>
            </Space>
          </Space>
        }
        styles={{
          header: { borderBottom: 'none', paddingBottom: 0 },
          body: { paddingTop: 16 },
        }}
      >
        <div style={{ marginBottom: 12 }}>
          <Checkbox
            checked={includeDisabled}
            onChange={(e) => setIncludeDisabled(e.target.checked)}
          >
            Inclure les actions desactivees
          </Checkbox>
        </div>
        <Table
          columns={getActionsColumns(handleEdit, handleStatusChange, handleDelete, handleDeactivate, handleReactivate, isDark)}
          dataSource={actions}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          locale={{ emptyText: 'Aucune action dans le catalogue' }}
          rowClassName={(record) => record.status === 'disabled' ? 'action-row-disabled' : ''}
          onRow={(record) => ({
            style: record.status === 'disabled' ? { opacity: 0.6 } : undefined,
          })}
        />
      </Card>

      <ActionWizard
        open={modalOpen}
        onCancel={handleCancel}
        onSubmit={editAction ? handleEditSubmit : handleCreate}
        loading={submitting}
        error={submitError}
        editAction={editAction}
        onSuccess={handleSuccess}
        initialItemType={editAction ? undefined : wizardInitialItemType ?? undefined}
      />

      <Modal
        title="Confirmation de désactivation en cascade"
        open={cascadeModalOpen}
        onCancel={() => {
          setCascadeModalOpen(false);
          setCascadeAction(null);
          setCascadeWorkflows([]);
          setCascadeReason('');
        }}
        onOk={handleCascadeConfirm}
        okText="Confirmer la désactivation"
        okType="danger"
        cancelText="Annuler"
      >
        <p>
          L'action <strong>{cascadeAction?.name}</strong> est utilisée dans le(s) workflow(s) suivant(s).
          Si vous confirmez, <strong>l'action et ces workflows seront désactivés</strong> :
        </p>
        <ul style={{ marginBottom: 16 }}>
          {cascadeWorkflows.map((wf) => (
            <li key={wf.id}>
              {wf.name} <Tag>{wf.status}</Tag>
            </li>
          ))}
        </ul>
        <div>
          <Typography.Text type="secondary">Raison (optionnel) :</Typography.Text>
          <Input
            value={cascadeReason}
            onChange={(e) => setCascadeReason(e.target.value)}
            placeholder="Raison de la desactivation"
            style={{ width: '100%', marginTop: 4 }}
          />
        </div>
      </Modal>
    </>
  );
}
