/**
 * useEditExecution Hook — Story 26.6 AC3, Story 11.11 AC4
 *
 * Manages edit modal state and API call for scheduled execution date updates.
 * Story 11.11: Only date field is editable (scheduled_at for one-time, next_execution_date for recurring).
 */
import { useState, useCallback } from 'react';
import { App, Form } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

import { updateScheduledExecution } from '../services/scheduled_execution_service';
import { ApiError } from '../services/api_client';
import type { ScheduledExecutionListItem, ScheduledExecutionUpdateRequest } from '../types/api';

dayjs.extend(utc);

export interface UseEditExecutionReturn {
  executionToEdit: ScheduledExecutionListItem | null;
  editModalVisible: boolean;
  editLoading: boolean;
  editForm: FormInstance;
  openEditModal: (exec: ScheduledExecutionListItem) => void;
  closeEditModal: () => void;
  submitEdit: () => Promise<void>;
}

export function useEditExecution(
  onSuccess: () => void,
  onClosePopover?: () => void,
): UseEditExecutionReturn {
  const { notification } = App.useApp();
  const [editForm] = Form.useForm();

  const [executionToEdit, setExecutionToEdit] = useState<ScheduledExecutionListItem | null>(null);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editLoading, setEditLoading] = useState(false);

  const openEditModal = useCallback((exec: ScheduledExecutionListItem) => {
    setExecutionToEdit(exec);
    setEditModalVisible(true);
    const isRecurring = !!exec.recurring_pattern;
    // API renvoie UTC ; on affiche en heure locale (comme SchedulingPanel)
    if (isRecurring) {
      editForm.setFieldsValue({
        next_execution_date: exec.recurring_pattern?.next_execution_date
          ? dayjs(exec.recurring_pattern.next_execution_date)
          : undefined,
      });
    } else {
      editForm.setFieldsValue({
        scheduled_at: exec.scheduled_at ? dayjs(exec.scheduled_at) : undefined,
      });
    }
  }, [editForm]);

  const closeEditModal = useCallback(() => {
    setEditModalVisible(false);
    setExecutionToEdit(null);
  }, []);

  const submitEdit = useCallback(async () => {
    if (!executionToEdit) return;
    try {
      const values = await editForm.validateFields();
      const isRecurring = !!executionToEdit.recurring_pattern;
      const payload: ScheduledExecutionUpdateRequest = {};

      if (isRecurring && values.next_execution_date) {
        payload.next_execution_date = values.next_execution_date.utc().format();
      } else if (!isRecurring && values.scheduled_at) {
        payload.scheduled_at = values.scheduled_at.utc().format();
      }

      setEditLoading(true);
      await updateScheduledExecution(executionToEdit.scheduled_execution_id, payload);
      notification.success({ message: 'Succès', description: 'Exécution planifiée modifiée avec succès' });
      setEditModalVisible(false);
      setExecutionToEdit(null);
      onClosePopover?.();
      onSuccess();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) return; // form validation
      const apiErr = err instanceof ApiError ? err : null;
      const status = apiErr?.status;
      const msg = (err as Error).message ?? '';
      const errorBody = apiErr?.responseBody?.error;
      const description = (errorBody?.message ?? msg) || "Une erreur est survenue lors de la modification";
      if (status === 403) {
        notification.error({ message: 'Permission refusée', description: "Vous n'avez pas la permission de modifier cette exécution planifiée" });
      } else if (status === 404) {
        notification.error({ message: 'Erreur', description: 'Exécution planifiée introuvable' });
      } else if (status === 400) {
        notification.error({ message: 'Erreur de validation', description });
      } else {
        notification.error({ message: 'Erreur', description });
      }
    } finally {
      setEditLoading(false);
    }
  }, [executionToEdit, editForm, onClosePopover, onSuccess, notification]);

  return {
    executionToEdit,
    editModalVisible,
    editLoading,
    editForm,
    openEditModal,
    closeEditModal,
    submitEdit,
  };
}
