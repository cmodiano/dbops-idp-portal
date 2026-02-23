/**
 * SchedulingPanel - Scheduling options panel extracted from ExecutionWizard.
 * Story 17.2, Task 3.1.
 *
 * Handles scheduling type selection (one-time, daily, weekly, cron)
 * and associated form controls.
 */

import { memo, useCallback } from 'react';
import {
  Form,
  Select,
  Input,
  DatePicker,
  Alert,
  Space,
  Tooltip,
  Radio,
  Button,
} from 'antd';
import {
  InfoCircleOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { CRON_PRESETS } from '../../utils/cronHelper';
import CronExpressionHelper from '../shared/CronExpressionHelper';
import type { SchedulingState } from '../../hooks/useExecutionSubmit';
import type { UseSchedulingValidationReturn } from '../../hooks/useSchedulingValidation';

export interface SchedulingPanelProps {
  scheduling: SchedulingState;
  onSchedulingChange: (updates: Partial<SchedulingState>) => void;
  schedulingError: string | null;
  submitting: boolean;
  validation: UseSchedulingValidationReturn;
}

export const SchedulingPanel = memo(function SchedulingPanel({
  scheduling,
  onSchedulingChange,
  schedulingError,
  submitting,
  validation,
}: SchedulingPanelProps) {
  const {
    schedulingType,
    scheduledAt,
    dailyHour,
    dailyMinute,
    weeklyDayOfWeek,
    weeklyHour,
    weeklyMinute,
    cronExpression,
    cronIsValid,
    cronError,
    cronNextExecutions,
    cronValidating,
    showCronHelper,
  } = scheduling;

  const handleCronChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const expression = e.target.value;
      onSchedulingChange({ cronExpression: expression });
      validation.validateCronDebounced(expression, (result) => {
        onSchedulingChange({
          cronIsValid: result.isValid,
          cronError: result.error,
          cronNextExecutions: result.nextExecutions,
          cronValidating: result.validating,
        });
      });
    },
    [onSchedulingChange, validation]
  );

  const handleCronPresetChange = useCallback(
    (value: string) => {
      if (value === 'custom') {
        onSchedulingChange({
          cronExpression: '',
          cronIsValid: null,
          cronNextExecutions: [],
        });
      } else {
        onSchedulingChange({ cronExpression: value });
        validation.validateCronDebounced(value, (result) => {
          onSchedulingChange({
            cronIsValid: result.isValid,
            cronError: result.error,
            cronNextExecutions: result.nextExecutions,
            cronValidating: result.validating,
          });
        });
      }
    },
    [onSchedulingChange, validation]
  );

  return (
    <div style={{ marginTop: 16 }}>
      <Form.Item label="Type de planification" required>
        <Radio.Group
          value={schedulingType}
          onChange={(e) => onSchedulingChange({ schedulingType: e.target.value })}
          disabled={submitting}
        >
          <Radio value="one-time">Une seule fois</Radio>
          <Radio value="daily">Tous les jours</Radio>
          <Radio value="weekly">Toutes les semaines</Radio>
          <Radio value="cron">Avancé (cron)</Radio>
        </Radio.Group>
      </Form.Item>

      {schedulingType === 'one-time' && (
        <Form.Item
          label="Date et heure d'exécution"
          required
          validateStatus={schedulingError ? 'error' : undefined}
          help={schedulingError}
        >
          <Space align="start">
            <DatePicker
              showTime={{ format: 'HH:mm' }}
              format="DD/MM/YYYY HH:mm"
              value={scheduledAt}
              onChange={(date) => onSchedulingChange({ scheduledAt: date })}
              disabledDate={(current) => current && current.isBefore(dayjs())}
              disabled={submitting}
              style={{ width: 220 }}
              placeholder="Sélectionner une date/heure"
              aria-label="Date et heure d'exécution planifiée"
            />
            <Tooltip title="Heure locale. Convertie automatiquement en UTC pour le stockage.">
              <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
            </Tooltip>
          </Space>
        </Form.Item>
      )}

      {schedulingType === 'daily' && (
        <Form.Item label="Heure d'exécution (heure locale)" required>
          <Space>
            <Select
              value={dailyHour}
              onChange={(v) => onSchedulingChange({ dailyHour: v })}
              style={{ width: 100 }}
              disabled={submitting}
              aria-label="Heure"
            >
              {Array.from({ length: 24 }, (_, i) => (
                <Select.Option key={i} value={i}>
                  {String(i).padStart(2, '0')}h
                </Select.Option>
              ))}
            </Select>
            <Select
              value={dailyMinute}
              onChange={(v) => onSchedulingChange({ dailyMinute: v })}
              style={{ width: 100 }}
              disabled={submitting}
              aria-label="Minutes"
            >
              {[0, 15, 30, 45].map((m) => (
                <Select.Option key={m} value={m}>
                  {String(m).padStart(2, '0')}min
                </Select.Option>
              ))}
            </Select>
            <Tooltip title="Heure locale. Convertie en UTC pour le stockage.">
              <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
            </Tooltip>
          </Space>
        </Form.Item>
      )}

      {schedulingType === 'weekly' && (
        <Form.Item label="Jour et heure (heure locale)" required>
          <Space>
            <Select
              value={weeklyDayOfWeek}
              onChange={(v) => onSchedulingChange({ weeklyDayOfWeek: v })}
              style={{ width: 120 }}
              disabled={submitting}
              aria-label="Jour de la semaine"
            >
              <Select.Option value={1}>Lundi</Select.Option>
              <Select.Option value={2}>Mardi</Select.Option>
              <Select.Option value={3}>Mercredi</Select.Option>
              <Select.Option value={4}>Jeudi</Select.Option>
              <Select.Option value={5}>Vendredi</Select.Option>
              <Select.Option value={6}>Samedi</Select.Option>
              <Select.Option value={7}>Dimanche</Select.Option>
            </Select>
            <Select
              value={weeklyHour}
              onChange={(v) => onSchedulingChange({ weeklyHour: v })}
              style={{ width: 100 }}
              disabled={submitting}
              aria-label="Heure"
            >
              {Array.from({ length: 24 }, (_, i) => (
                <Select.Option key={i} value={i}>
                  {String(i).padStart(2, '0')}h
                </Select.Option>
              ))}
            </Select>
            <Select
              value={weeklyMinute}
              onChange={(v) => onSchedulingChange({ weeklyMinute: v })}
              style={{ width: 100 }}
              disabled={submitting}
              aria-label="Minutes"
            >
              {[0, 15, 30, 45].map((m) => (
                <Select.Option key={m} value={m}>
                  {String(m).padStart(2, '0')}min
                </Select.Option>
              ))}
            </Select>
            <Tooltip title="Heure locale. Convertie en UTC pour le stockage.">
              <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
            </Tooltip>
          </Space>
        </Form.Item>
      )}

      {schedulingType === 'cron' && (
        <div>
          <Form.Item
            label="Expression cron"
            required
            validateStatus={cronIsValid === false ? 'error' : cronIsValid === true ? 'success' : undefined}
            help={cronError || undefined}
          >
            <Space orientation="vertical" style={{ width: '100%' }}>
              <Space>
                <Select
                  placeholder="Préréglages courants"
                  onChange={handleCronPresetChange}
                  style={{ width: 200 }}
                  disabled={submitting}
                  aria-label="Préréglages cron"
                  allowClear
                  value={CRON_PRESETS.some((p) => p.value === cronExpression) ? cronExpression : undefined}
                >
                  {CRON_PRESETS.map((preset) => (
                    <Select.Option key={preset.value} value={preset.value}>
                      {preset.label}
                    </Select.Option>
                  ))}
                </Select>
                <Tooltip title="Aide sur les expressions cron">
                  <Button
                    type="link"
                    icon={<QuestionCircleOutlined />}
                    onClick={() => onSchedulingChange({ showCronHelper: true })}
                    style={{ padding: 0 }}
                  >
                    Aide
                  </Button>
                </Tooltip>
              </Space>
              <Input
                value={cronExpression}
                onChange={handleCronChange}
                placeholder="minute heure jour mois jour_semaine (ex: 0 2 * * 1-5)"
                disabled={submitting}
                aria-label="Expression cron"
                suffix={
                  cronValidating ? (
                    <LoadingOutlined style={{ color: '#1890ff' }} />
                  ) : cronIsValid === true ? (
                    <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  ) : cronIsValid === false ? (
                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                  ) : null
                }
              />
            </Space>
          </Form.Item>

          {cronIsValid && cronNextExecutions.length > 0 && (
            <Alert
              type="info"
              showIcon
              icon={<ClockCircleOutlined />}
              message="Prochaines exécutions (UTC)"
              description={
                <ul style={{ margin: '8px 0 0 0', paddingLeft: 20 }}>
                  {cronNextExecutions.map((exec, i) => (
                    <li key={i}>
                      {dayjs(exec).utc().format('DD/MM/YYYY HH:mm')}
                    </li>
                  ))}
                </ul>
              }
              style={{ marginBottom: 16 }}
            />
          )}
        </div>
      )}

      {schedulingError && (
        <Alert
          message="Erreur de planification"
          description={schedulingError}
          type="error"
          showIcon
          role="alert"
          aria-live="assertive"
          style={{ marginTop: 16 }}
        />
      )}

      <CronExpressionHelper
        open={showCronHelper}
        onClose={() => onSchedulingChange({ showCronHelper: false })}
      />
    </div>
  );
});
