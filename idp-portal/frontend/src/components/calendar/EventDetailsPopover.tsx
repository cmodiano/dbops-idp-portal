/**
 * EventDetailsPopover — Story 26.6 AC5
 *
 * Extracted from CalendarPage.tsx. Displays scheduled execution details
 * in a popover with RBAC-controlled cancel/edit/toggle actions.
 */
import { Link } from 'react-router';
import { Typography, Tag, Space, Descriptions, Button, Switch } from 'antd';
import { SyncOutlined, ClockCircleOutlined, LinkOutlined } from '@ant-design/icons';

import { FormattedJson } from '../common/FormattedJson';
import { useAuth } from '../../contexts/AuthContext';
import { getDisplayParameters, describePatternType } from '../../utils/calendarEventUtils';
import { getEnvironmentHexColor, getEnvironmentLabel } from '../../utils/environmentHelpers';
import { formatUtcToLocal } from '../../utils/dateFormat';
import type { ScheduledExecutionListItem } from '../../types/api';

const { Text } = Typography;

export interface EventDetailsPopoverProps {
  execution: ScheduledExecutionListItem;
  onRequestCancel?: (exec: ScheduledExecutionListItem) => void;
  onRequestEdit?: (exec: ScheduledExecutionListItem) => void;
  onToggleRecurrence?: (id: number, currentState: boolean) => void;
  cancelLoading?: boolean;
  editLoading?: boolean;
  togglingPatternId?: number | null;
}

export function EventDetailsPopover({
  execution,
  onRequestCancel,
  onRequestEdit,
  onToggleRecurrence,
  cancelLoading = false,
  editLoading = false,
  togglingPatternId = null,
}: EventDetailsPopoverProps) {
  const { user } = useAuth();
  const effectiveDate = execution.recurring_pattern?.next_execution_date ?? execution.scheduled_at;
  const isRecurring = !!execution.recurring_pattern;
  const targets = (execution.parameters?._targets as string[] | undefined) ?? [];
  const hasTargets = Array.isArray(targets) && targets.length > 0;
  const displayParams = getDisplayParameters(execution.parameters ?? null);
  const hasDisplayParams = Object.keys(displayParams).length > 0;
  const showExecutionLink =
    execution.status === 'executed' &&
    execution.execution_id != null;
  // Story 57.17: lien vers l'exécution source (créée via schedule_execution step)
  const showOriginLink = execution.source_execution_id != null;
  const isDbops = user?.profile?.toLowerCase() === 'dbops';
  const canCancel =
    execution.status === 'pending' &&
    onRequestCancel != null &&
    (execution.user_id === user?.id || isDbops);
  const canEdit =
    execution.status === 'pending' &&
    onRequestEdit != null &&
    (execution.user_id === user?.id || isDbops);
  const showRecurrenceToggle =
    isDbops &&
    isRecurring &&
    execution.recurring_pattern != null &&
    onToggleRecurrence != null;
  const toggling = togglingPatternId === execution.scheduled_execution_id;

  return (
    <div style={{ maxWidth: 400 }} data-testid="event-details-popover">
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Action">
          {execution.action_name}
          {execution.action_id != null && (
            <Text type="secondary" style={{ marginLeft: 8 }}>(ID {execution.action_id})</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Environnement">
          <Tag color={getEnvironmentHexColor(execution.environment ?? '')}>
            {getEnvironmentLabel(execution.environment ?? '')}
          </Tag>
        </Descriptions.Item>
        {hasTargets && (
          <Descriptions.Item label="Targets">
            <Space size={[0, 4]} wrap>
              {targets.map((t) => (
                <Tag key={t} color="blue">{t}</Tag>
              ))}
            </Space>
          </Descriptions.Item>
        )}
        {hasDisplayParams && (
          <Descriptions.Item label="Paramètres">
            <div data-testid="popover-parameters" style={{ maxWidth: 360 }}>
              <FormattedJson
                value={displayParams}
                style={{
                  margin: 0,
                  padding: 8,
                  fontSize: 12,
                  overflow: 'auto',
                  background: 'var(--ant-color-fill-quaternary)',
                  borderRadius: 4,
                }}
              />
            </div>
          </Descriptions.Item>
        )}
        <Descriptions.Item label="Utilisateur">
          {execution.user_name}
          {execution.user_id != null && (
            <Text type="secondary" style={{ marginLeft: 8 }}>(ID {execution.user_id})</Text>
          )}
        </Descriptions.Item>
        <Descriptions.Item label="Date/heure">
          <Space>
            <ClockCircleOutlined />
            {formatUtcToLocal(effectiveDate ?? null)}
          </Space>
        </Descriptions.Item>
        <Descriptions.Item label="Type">
          <Space>
            {isRecurring && <SyncOutlined />}
            {describePatternType(execution)}
          </Space>
        </Descriptions.Item>
        {execution.platform != null && execution.platform !== '' && (
          <Descriptions.Item label="Plateforme">{execution.platform}</Descriptions.Item>
        )}
        {execution.engine != null && execution.engine !== '' && (
          <Descriptions.Item label="Technologie">{execution.engine}</Descriptions.Item>
        )}
        {execution.status && (
          <Descriptions.Item label="Statut">
            <Tag color={execution.status === 'pending' ? 'blue' : execution.status === 'executed' ? 'green' : 'default'}>
              {execution.status === 'pending' ? 'En attente' : execution.status === 'executed' ? 'Exécutée' : execution.status === 'cancelled' ? 'Annulée' : execution.status}
            </Tag>
          </Descriptions.Item>
        )}
        {showExecutionLink && (
          <Descriptions.Item label="Exécution">
            <Link to={`/executions/${execution.execution_id}`} data-testid="link-to-execution">
              <LinkOutlined /> Voir l'exécution
            </Link>
          </Descriptions.Item>
        )}
        {showOriginLink && (
          <Descriptions.Item label="Origine">
            <Link
              to={`/executions/${execution.source_execution_id}`}
              data-testid="link-to-source-execution"
            >
              <LinkOutlined /> Voir l'exécution source
            </Link>
          </Descriptions.Item>
        )}
      </Descriptions>
      {showRecurrenceToggle && (
        <div style={{ marginTop: 12 }}>
          <Space>
            <Switch
              checked={execution.recurring_pattern?.is_active ?? false}
              onChange={() =>
                onToggleRecurrence?.(execution.scheduled_execution_id, !(execution.recurring_pattern?.is_active ?? false))
              }
              loading={toggling}
              data-testid="recurrence-toggle"
            />
            <span data-testid="recurrence-toggle-label">
              {execution.recurring_pattern?.is_active ? 'Récurrence active' : 'Récurrence inactive'}
            </span>
          </Space>
        </div>
      )}
      {(canCancel || canEdit) && (
        <div style={{ marginTop: 12, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          {canEdit && (
            <Button
              type="default"
              loading={editLoading}
              onClick={() => onRequestEdit?.(execution)}
              data-testid="edit-execution-btn"
            >
              Modifier
            </Button>
          )}
          {canCancel && (
            <Button
              type="primary"
              danger
              loading={cancelLoading}
              onClick={() => onRequestCancel?.(execution)}
              data-testid="cancel-execution-btn"
            >
              Annuler
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
