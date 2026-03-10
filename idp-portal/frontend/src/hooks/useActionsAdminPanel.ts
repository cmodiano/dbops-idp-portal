/**
 * useActionsAdminPanel — Encapsulation DIP du state et des handlers CRUD de ActionsAdminPanel.
 * Story 48.8 (SOLID-FE-4, AC5): Supprime les imports directs de fonctions runtime admin_service dans ActionsAdminPanel.tsx.
 * Code review: cancelled flag pour éviter setState sur composant démonté lors de fetchActions.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { App } from 'antd';
import {
  createAction,
  getAction,
  getAdminActions,
  updateAction,
  updateActionStatus,
  deleteAction,
  deactivateAction,
  reactivateAction,
} from '../services/admin_service';
import type { DeactivateConfirmation } from '../services/admin_service';
import type {
  ActionCreate,
  ActionListItem,
  ActionDetail,
  ActionResponse,
  StatusTransition,
  AdminActionsFilters,
} from '../types/api';

type NotificationInstance = ReturnType<typeof App.useApp>['notification'];
type ModalHookAPI = ReturnType<typeof App.useApp>['modal'];

export interface UseActionsAdminPanelOptions {
  notification: NotificationInstance;
  modal: ModalHookAPI;
}

export interface UseActionsAdminPanelReturn {
  // State exposé
  actions: ActionListItem[];
  loading: boolean;
  modalOpen: boolean;
  submitting: boolean;
  submitError: string | null;
  editAction: ActionDetail | null;
  wizardInitialItemType: 'action' | 'workflow' | null;
  cascadeModalOpen: boolean;
  cascadeAction: ActionListItem | null;
  cascadeWorkflows: { id: number; name: string; status: string }[];
  cascadeReason: string;
  setCascadeReason: (v: string) => void;
  // Handlers
  fetchActions: (filters?: AdminActionsFilters) => Promise<void>;
  handleCreate: (action: ActionCreate) => Promise<ActionResponse>;
  handleEditSubmit: (action: ActionCreate) => Promise<ActionDetail>;
  handleEdit: (record: ActionListItem) => Promise<void>;
  handleStatusChange: (record: ActionListItem, transition: StatusTransition) => Promise<void>;
  handleDelete: (record: ActionListItem) => void;
  handleDeactivate: (record: ActionListItem) => Promise<void>;
  handleReactivate: (record: ActionListItem) => Promise<void>;
  openCreateAction: () => void;
  openCreateWorkflow: () => void;
  handleModalClose: () => void;
  handleSuccess: (action: ActionDetail | ActionResponse | ActionListItem) => void;
  handleCascadeConfirm: () => Promise<void>;
  handleCascadeCancel: () => void;
}

export function useActionsAdminPanel({ notification, modal }: UseActionsAdminPanelOptions): UseActionsAdminPanelReturn {
  const [actions, setActions] = useState<ActionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [editAction, setEditAction] = useState<ActionDetail | null>(null);
  const [wizardInitialItemType, setWizardInitialItemType] = useState<'action' | 'workflow' | null>(null);

  const [cascadeModalOpen, setCascadeModalOpen] = useState(false);
  const [cascadeAction, setCascadeAction] = useState<ActionListItem | null>(null);
  const [cascadeWorkflows, setCascadeWorkflows] = useState<{ id: number; name: string; status: string }[]>([]);
  const [cascadeReason, setCascadeReason] = useState<string>('');

  const cancelledRef = useRef(false);
  useEffect(() => () => {
    cancelledRef.current = true;
  }, []);

  const fetchActions = useCallback(async (filters?: AdminActionsFilters) => {
    setLoading(true);
    try {
      const mergedFilters: AdminActionsFilters = { ...filters, include_disabled: true };
      const response = await getAdminActions(mergedFilters);
      if (!cancelledRef.current) setActions(response.data ?? []);
    } catch (err) {
      if (!cancelledRef.current) {
        notification.error({
          title: 'Erreur',
          description: err instanceof Error ? err.message : 'Erreur de chargement',
        });
      }
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  }, [notification]);

  const handleCreate = async (action: ActionCreate): Promise<ActionResponse> => {
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

  const handleEditSubmit = async (action: ActionCreate): Promise<ActionDetail> => {
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
        description: err instanceof Error ? err.message : "Impossible de charger l'action",
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
      title: "Supprimer l'action",
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
            description: err instanceof Error ? err.message : "Impossible de supprimer l'action",
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
        description: err instanceof Error ? err.message : "Impossible de desactiver l'action",
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
        description: err instanceof Error ? err.message : "Impossible de desactiver l'action",
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
        description: err instanceof Error ? err.message : "Impossible de reactiver l'action",
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

  const handleModalClose = () => {
    setModalOpen(false);
    setEditAction(null);
    setWizardInitialItemType(null);
    setSubmitError(null);
  };

  const openCreateAction = () => {
    setEditAction(null);
    setWizardInitialItemType('action');
    setModalOpen(true);
  };

  const openCreateWorkflow = () => {
    setEditAction(null);
    setWizardInitialItemType('workflow');
    setModalOpen(true);
  };

  const handleCascadeCancel = () => {
    setCascadeModalOpen(false);
    setCascadeAction(null);
    setCascadeWorkflows([]);
    setCascadeReason('');
  };

  return {
    actions,
    loading,
    modalOpen,
    submitting,
    submitError,
    editAction,
    wizardInitialItemType,
    cascadeModalOpen,
    cascadeAction,
    cascadeWorkflows,
    cascadeReason,
    setCascadeReason,
    fetchActions,
    handleCreate,
    handleEditSubmit,
    handleEdit,
    handleStatusChange,
    handleDelete,
    handleDeactivate,
    handleReactivate,
    openCreateAction,
    openCreateWorkflow,
    handleModalClose,
    handleSuccess,
    handleCascadeConfirm,
    handleCascadeCancel,
  };
}
