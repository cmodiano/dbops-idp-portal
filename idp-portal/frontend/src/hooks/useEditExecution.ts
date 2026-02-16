/**
 * useEditExecution Hook — Story 26.6 AC3
 *
 * Extracted from CalendarPage.tsx. Manages edit modal state, form instance,
 * target options loading, and API call for scheduled execution updates.
 */
import { useState, useCallback, useEffect } from 'react';
import { App, Form } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';

import { updateScheduledExecution } from '../services/scheduled_execution_service';
import { fetchInventoryTargets } from '../services/execution_service';
import { ApiError } from '../services/api_client';
import { useAuth } from '../contexts/AuthContext';
import { getDisplayParameters } from '../utils/calendarEventUtils';
import type { ScheduledExecutionListItem, ExecutionEnvironment, ScheduledExecutionUpdateRequest } from '../types/api';

dayjs.extend(utc);

export interface UseEditExecutionReturn {
  executionToEdit: ScheduledExecutionListItem | null;
  editModalVisible: boolean;
  editLoading: boolean;
  editForm: FormInstance;
  targetOptions: { label: string; value: string }[];
  openEditModal: (exec: ScheduledExecutionListItem) => void;
  closeEditModal: () => void;
  submitEdit: () => Promise<void>;
}

export function useEditExecution(
  onSuccess: () => void,
  onClosePopover?: () => void,
): UseEditExecutionReturn {
  const { notification } = App.useApp();
  const { user } = useAuth();
  const [editForm] = Form.useForm();

  const [executionToEdit, setExecutionToEdit] = useState<ScheduledExecutionListItem | null>(null);
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [targetOptions, setTargetOptions] = useState<{ label: string; value: string }[]>([]);

  const openEditModal = useCallback((exec: ScheduledExecutionListItem) => {
    setExecutionToEdit(exec);
    setEditModalVisible(true);
    const targets = (exec.parameters?._targets as string[] | undefined) ?? [];
    const rp = exec.recurring_pattern;
    const pc = rp?.pattern_config as { hour?: number; minute?: number; day_of_week?: number; cron_expression?: string } | undefined;
    editForm.setFieldsValue({
      scheduled_at: exec.scheduled_at ? dayjs.utc(exec.scheduled_at) : undefined,
      parameters_json: JSON.stringify(getDisplayParameters(exec.parameters ?? null), null, 2),
      target_names: Array.isArray(targets) ? targets : [],
      environment: exec.environment,
      pattern_type: rp?.pattern_type ?? 'daily',
      pattern_hour: pc?.hour ?? 0,
      pattern_minute: pc?.minute ?? 0,
      pattern_day_of_week: pc?.day_of_week ?? 1,
      cron_expression: pc?.cron_expression ?? '',
    });
  }, [editForm]);

  const closeEditModal = useCallback(() => {
    setEditModalVisible(false);
    setExecutionToEdit(null);
  }, []);

  // Load target options when edit modal opens
  useEffect(() => {
    if (!editModalVisible || !executionToEdit || !user) return;
    fetchInventoryTargets()
      .then((items) => setTargetOptions(items.map((t) => ({ label: `${t.name} (${t.environment})`, value: t.name }))))
      .catch(() => setTargetOptions([]));
  }, [editModalVisible, executionToEdit, user]);

  const submitEdit = useCallback(async () => {
    if (!executionToEdit) return;
    try {
      const values = await editForm.validateFields();
      const payload: ScheduledExecutionUpdateRequest = {};
      const isRecurring = !!executionToEdit.recurring_pattern;

      if (!isRecurring && values.scheduled_at) {
        payload.scheduled_at = values.scheduled_at.utc().format();
      }
      if (values.parameters_json) {
        try {
          const parsed = JSON.parse(values.parameters_json as string);
          if (parsed && typeof parsed === 'object') {
            const existing = executionToEdit.parameters ?? {};
            payload.parameters = { ...existing, ...parsed };
          }
        } catch {
          // keep existing params if JSON invalid
        }
      }
      if (values.target_names != null && Array.isArray(values.target_names)) {
        payload.target_names = values.target_names;
      }
      if (payload.target_names == null && values.environment) {
        payload.environment = values.environment as ExecutionEnvironment;
      }
      if (isRecurring && values.pattern_type) {
        const patternType = values.pattern_type as 'daily' | 'weekly' | 'cron';
        if (patternType === 'cron' && values.cron_expression) {
          payload.recurring_pattern = { pattern_type: 'cron', pattern_config: { cron_expression: values.cron_expression } };
        } else if (patternType === 'daily') {
          payload.recurring_pattern = {
            pattern_type: 'daily',
            pattern_config: { hour: values.pattern_hour ?? 0, minute: values.pattern_minute ?? 0 },
          };
        } else if (patternType === 'weekly') {
          payload.recurring_pattern = {
            pattern_type: 'weekly',
            pattern_config: {
              day_of_week: values.pattern_day_of_week ?? 1,
              hour: values.pattern_hour ?? 0,
              minute: values.pattern_minute ?? 0,
            },
          };
        }
      }

      setEditLoading(true);
      await updateScheduledExecution(executionToEdit.scheduled_execution_id, payload);
      notification.success({ title: 'Succès', description: 'Exécution planifiée modifiée avec succès' });
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
      if (status === 400 && errorBody?.details && typeof errorBody.details === 'object') {
        const details = errorBody.details as Record<string, unknown>;
        editForm.setFields(
          Object.entries(details).map(([name, value]) => ({
            name,
            errors: [typeof value === 'string' ? value : JSON.stringify(value)],
          }))
        );
      }
      if (status === 403) {
        notification.error({ title: 'Permission refusée', description: "Vous n'avez pas la permission de modifier cette exécution planifiée" });
      } else if (status === 404) {
        notification.error({ title: 'Erreur', description: 'Exécution planifiée introuvable' });
      } else if (status === 400) {
        notification.error({ title: 'Erreur de validation', description });
      } else {
        notification.error({ title: 'Erreur', description });
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
    targetOptions,
    openEditModal,
    closeEditModal,
    submitEdit,
  };
}
