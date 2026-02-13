/**
 * CancelExecutionModal — Story 26.6
 *
 * Confirmation modal for cancelling a scheduled execution.
 */
import { Modal, Button, Descriptions, Tag, Typography } from 'antd';

import { ENV_COLORS, ENV_LABELS } from '../../utils/calendarEventUtils';
import { formatUtcToLocal } from '../../utils/dateFormat';
import type { ScheduledExecutionListItem } from '../../types/api';

const { Text } = Typography;

export interface CancelExecutionModalProps {
  execution: ScheduledExecutionListItem | null;
  open: boolean;
  loading: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function CancelExecutionModal({ execution, open, loading, onCancel, onConfirm }: CancelExecutionModalProps) {
  return (
    <Modal
      title="Confirmer l'annulation"
      open={open}
      zIndex={1100}
      onCancel={onCancel}
      footer={[
        <Button key="back" onClick={onCancel}>
          Annuler
        </Button>,
        <Button
          key="confirm"
          type="primary"
          danger
          loading={loading}
          onClick={onConfirm}
          data-testid="confirm-cancel-execution-btn"
        >
          Confirmer l'annulation
        </Button>,
      ]}
      data-testid="cancel-execution-modal"
    >
      {execution && (
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="Action">{execution.action_name}</Descriptions.Item>
          <Descriptions.Item label="Date planifiée">
            {formatUtcToLocal(execution.recurring_pattern?.next_execution_date ?? execution.scheduled_at ?? null)}
          </Descriptions.Item>
          <Descriptions.Item label="Utilisateur">{execution.user_name}</Descriptions.Item>
          <Descriptions.Item label="Environnement">
            <Tag color={ENV_COLORS[execution.environment]}>
              {ENV_LABELS[execution.environment] ?? execution.environment}
            </Tag>
          </Descriptions.Item>
        </Descriptions>
      )}
      {execution?.recurring_pattern && (
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          Il s'agit d'une annulation de l'occurrence unique (la récurrence reste active).
        </Text>
      )}
    </Modal>
  );
}
