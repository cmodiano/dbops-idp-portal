/**
 * useCancelExecution Hook — Story 26.6 AC2
 *
 * Extracted from CalendarPage.tsx. Manages cancel modal state and API call
 * for scheduled execution cancellation.
 */
import { useState, useCallback } from 'react';
import { App } from 'antd';
import { cancelScheduledExecution } from '../services/scheduled_execution_service';
import { ApiError } from '../services/api_client';
import type { ScheduledExecutionListItem } from '../types/api';

export interface UseCancelExecutionReturn {
  executionToCancel: ScheduledExecutionListItem | null;
  cancelModalVisible: boolean;
  cancelLoading: boolean;
  openCancelModal: (exec: ScheduledExecutionListItem) => void;
  closeCancelModal: () => void;
  confirmCancel: () => Promise<void>;
}

export function useCancelExecution(
  onSuccess: () => void,
  onClosePopover?: () => void,
): UseCancelExecutionReturn {
  const { notification } = App.useApp();

  const [executionToCancel, setExecutionToCancel] = useState<ScheduledExecutionListItem | null>(null);
  const [cancelModalVisible, setCancelModalVisible] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);

  const openCancelModal = useCallback((exec: ScheduledExecutionListItem) => {
    setExecutionToCancel(exec);
    setCancelModalVisible(true);
  }, []);

  const closeCancelModal = useCallback(() => {
    setCancelModalVisible(false);
    setExecutionToCancel(null);
  }, []);

  const confirmCancel = useCallback(async () => {
    if (!executionToCancel) return;
    setCancelLoading(true);
    try {
      await cancelScheduledExecution(executionToCancel.scheduled_execution_id);
      notification.success({
        message: 'Succès',
        description: 'Exécution planifiée annulée avec succès',
      });
      setCancelModalVisible(false);
      setExecutionToCancel(null);
      onClosePopover?.();
      onSuccess();
    } catch (err: unknown) {
      const status = err instanceof ApiError ? err.status : undefined;
      const msg = (err as Error).message ?? '';
      if (status === 403 || (!status && (msg.includes('permission') || msg.includes('refusée') || msg.includes('Permission')))) {
        notification.error({
          message: 'Permission refusée',
          description: "Vous n'avez pas la permission d'annuler cette exécution",
        });
      } else if (status === 400 || (!status && (msg.includes('attente') || msg.includes('modifiées') || msg.includes('status') || msg.includes('INVALID')))) {
        notification.error({
          message: 'Erreur',
          description: 'Cette exécution ne peut plus être annulée',
        });
      } else {
        notification.error({
          message: 'Erreur',
          description: msg || "Une erreur est survenue lors de l'annulation",
        });
      }
    } finally {
      setCancelLoading(false);
    }
  }, [executionToCancel, onClosePopover, onSuccess, notification]);

  return {
    executionToCancel,
    cancelModalVisible,
    cancelLoading,
    openCancelModal,
    closeCancelModal,
    confirmCancel,
  };
}
