/**
 * EditExecutionModal — Story 26.6
 *
 * Modal for editing a scheduled execution (date, targets, pattern, params).
 */
import { Modal, Button, Form, DatePicker, Input, Select, Radio, Space } from 'antd';
import type { FormInstance } from 'antd';
import dayjs from 'dayjs';

import { ENV_LABELS } from '../../utils/calendarEventUtils';
import type { ScheduledExecutionListItem } from '../../types/api';

export interface EditExecutionModalProps {
  execution: ScheduledExecutionListItem | null;
  open: boolean;
  loading: boolean;
  form: FormInstance;
  targetOptions: { label: string; value: string }[];
  onCancel: () => void;
  onSubmit: () => void;
}

export function EditExecutionModal({ execution, open, loading, form, targetOptions, onCancel, onSubmit }: EditExecutionModalProps) {
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
          {!execution.recurring_pattern ? (
            <Form.Item name="scheduled_at" label="Date/heure planifiée (UTC)" rules={[{ required: true, message: 'Requis' }]}>
              <DatePicker showTime format="DD/MM/YYYY HH:mm" style={{ width: '100%' }} disabledDate={(d) => d && d.isBefore(dayjs().startOf('minute'))} />
            </Form.Item>
          ) : (
            <>
              <Form.Item name="pattern_type" label="Type de récurrence">
                <Radio.Group options={[{ label: 'Quotidien', value: 'daily' }, { label: 'Hebdomadaire', value: 'weekly' }, { label: 'Cron', value: 'cron' }]} />
              </Form.Item>
              <Form.Item noStyle shouldUpdate={(prev, curr) => prev?.pattern_type !== curr?.pattern_type}>
                {({ getFieldValue }) =>
                  getFieldValue('pattern_type') === 'cron' ? (
                    <Form.Item name="cron_expression" label="Expression cron">
                      <Input placeholder="0 9 * * 1-5" />
                    </Form.Item>
                  ) : (
                    <Space>
                      {getFieldValue('pattern_type') === 'weekly' && (
                        <Form.Item name="pattern_day_of_week" label="Jour (1=Lu, 7=Di)">
                          <Select options={[1, 2, 3, 4, 5, 6, 7].map((d) => ({ label: ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'][d - 1], value: d }))} style={{ width: 100 }} />
                        </Form.Item>
                      )}
                      <Form.Item name="pattern_hour" label="Heure (UTC)">
                        <Select options={Array.from({ length: 24 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i }))} style={{ width: 70 }} />
                      </Form.Item>
                      <Form.Item name="pattern_minute" label="Minute">
                        <Select options={Array.from({ length: 60 }, (_, i) => ({ label: i.toString().padStart(2, '0'), value: i }))} style={{ width: 70 }} />
                      </Form.Item>
                    </Space>
                  )
                }
              </Form.Item>
            </>
          )}
          <Form.Item name="target_names" label="Targets">
            <Select mode="multiple" placeholder="Sélectionner les targets" options={targetOptions} allowClear showSearch optionFilterProp="label" />
          </Form.Item>
          <Form.Item name="environment" label="Environnement (si pas de targets)">
            <Select options={[{ label: ENV_LABELS.dev, value: 'dev' }, { label: ENV_LABELS.staging, value: 'staging' }, { label: ENV_LABELS.prod, value: 'prod' }]} />
          </Form.Item>
          <Form.Item name="parameters_json" label="Paramètres (JSON)">
            <Input.TextArea rows={4} placeholder='{"key": "value"}' />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
}
