/**
 * EditExecutionModal — Story 26.6, Story 11.11 AC4
 *
 * Modal for editing a scheduled execution date only.
 * Story 11.11: Only date field is editable (scheduled_at for one-time, next_execution_date for recurring).
 */
import { Modal, Button, Form, DatePicker } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';

import type { ScheduledExecutionListItem } from '../../types/api';

export interface EditExecutionModalProps {
  execution: ScheduledExecutionListItem | null;
  open: boolean;
  loading: boolean;
  form: FormInstance;
  onCancel: () => void;
  onSubmit: () => void;
}

export function EditExecutionModal({ execution, open, loading, form, onCancel, onSubmit }: EditExecutionModalProps) {
  const isRecurring = !!execution?.recurring_pattern;

  return (
    <Modal
      title="Modifier l'exécution planifiée"
      open={open}
      zIndex={1100}
      onCancel={onCancel}
      footer={[
        <Button key="back" onClick={onCancel}>
          Annuler
        </Button>,
        <Button key="submit" type="primary" loading={loading} onClick={onSubmit} data-testid="confirm-edit-execution-btn">
          Enregistrer
        </Button>,
      ]}
      width={560}
      data-testid="edit-execution-modal"
    >
      {execution && (
        <Form form={form} layout="vertical">
          {isRecurring ? (
            <Form.Item name="next_execution_date" label="Prochaine date d'exécution (heure locale)" rules={[{ required: true, message: 'Requis' }]}>
              <DatePicker showTime format="DD/MM/YYYY HH:mm" style={{ width: '100%' }} disabledDate={(d) => d && d.isBefore(dayjs().startOf('minute'))} />
            </Form.Item>
          ) : (
            <Form.Item name="scheduled_at" label="Date/heure planifiée (heure locale)" rules={[{ required: true, message: 'Requis' }]}>
              <DatePicker showTime format="DD/MM/YYYY HH:mm" style={{ width: '100%' }} disabledDate={(d) => d && d.isBefore(dayjs().startOf('minute'))} />
            </Form.Item>
          )}
        </Form>
      )}
    </Modal>
  );
}
