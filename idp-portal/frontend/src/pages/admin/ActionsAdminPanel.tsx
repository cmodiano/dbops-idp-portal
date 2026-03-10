import { useEffect } from 'react';
import { App, Typography, Button, Table, Space, Card, Tag, Modal, Input } from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';
import { ActionWizard } from '../../components/admin/ActionWizard';
import { useActionsAdminPanel } from '../../hooks/useActionsAdminPanel';
import { getActionsColumns } from './actionsColumns';

type NotificationInstance = ReturnType<typeof App.useApp>['notification'];
type ModalHookAPI = ReturnType<typeof App.useApp>['modal'];

export interface ActionsAdminPanelProps {
  notification: NotificationInstance;
  modal: ModalHookAPI;
  isDark: boolean;
}

export function ActionsAdminPanel({ notification, modal, isDark }: ActionsAdminPanelProps) {
  const panel = useActionsAdminPanel({ notification, modal });
  const { fetchActions } = panel;

  useEffect(() => {
    fetchActions();
  }, [fetchActions]);

  return (
    <>
      <Card
        title={
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <span>Actions ({panel.actions.length})</span>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => panel.fetchActions()} loading={panel.loading}>
                Actualiser
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={panel.openCreateAction}
              >
                Nouvelle action
              </Button>
              <Button
                icon={<ApartmentOutlined />}
                onClick={panel.openCreateWorkflow}
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
        <Table
          columns={getActionsColumns(panel.handleEdit, panel.handleStatusChange, panel.handleDelete, panel.handleDeactivate, panel.handleReactivate, isDark)}
          dataSource={panel.actions}
          rowKey="id"
          loading={panel.loading}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          locale={{ emptyText: 'Aucune action dans le catalogue' }}
          rowClassName={(record) => record.status === 'disabled' ? 'action-row-disabled' : ''}
          onRow={(record) => ({
            style: record.status === 'disabled' ? { opacity: 0.6 } : undefined,
          })}
        />
      </Card>

      <ActionWizard
        open={panel.modalOpen}
        onCancel={panel.handleModalClose}
        onSubmit={panel.editAction ? panel.handleEditSubmit : panel.handleCreate}
        loading={panel.submitting}
        error={panel.submitError}
        editAction={panel.editAction}
        onSuccess={panel.handleSuccess}
        initialItemType={panel.editAction ? undefined : panel.wizardInitialItemType ?? undefined}
      />

      <Modal
        title="Confirmation de désactivation en cascade"
        open={panel.cascadeModalOpen}
        onCancel={panel.handleCascadeCancel}
        onOk={panel.handleCascadeConfirm}
        okText="Confirmer la désactivation"
        okType="danger"
        cancelText="Annuler"
      >
        <p>
          L'action <strong>{panel.cascadeAction?.name}</strong> est utilisée dans le(s) workflow(s) suivant(s).
          Si vous confirmez, <strong>l'action et ces workflows seront désactivés</strong> :
        </p>
        <ul style={{ marginBottom: 16 }}>
          {panel.cascadeWorkflows.map((wf) => (
            <li key={wf.id}>
              {wf.name} <Tag>{wf.status}</Tag>
            </li>
          ))}
        </ul>
        <div>
          <Typography.Text type="secondary">Raison (optionnel) :</Typography.Text>
          <Input
            value={panel.cascadeReason}
            onChange={(e) => panel.setCascadeReason(e.target.value)}
            placeholder="Raison de la desactivation"
            style={{ width: '100%', marginTop: 4 }}
          />
        </div>
      </Modal>
    </>
  );
}
