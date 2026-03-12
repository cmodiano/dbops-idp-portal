/**
 * TimelineStepItem — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Renders a single step: icon, expand button, expanded detail, ServiceNow badge.
 */

import './TimelineList.css';
import { Button, Typography, Badge } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  MinusOutlined,
  ClockCircleOutlined,
  HourglassOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router';
import { STEP_STATUS_COLOR as STATUS_COLOR } from '../../../utils/execution-status';
import { formatDuration } from './utils';
import { formatUtcToLocal } from '../../../utils/dateFormat';
import type { ExecutionStepResponse } from '../../../types/api';
import { FormattedJson } from '../../common/FormattedJson';

const { Text } = Typography;

/** Résout le nom affiché : referenced_action_name, gate type (Approbation/Fenêtre maintenance), ou step_name. */
function getStepDisplayName(step: ExecutionStepResponse): string {
  const output = step.output as Record<string, unknown> | null | undefined;
  const refName = output?.referenced_action_name as string | undefined;
  if (refName) return refName;

  if (step.step_type === 'gate') {
    const gateType = output?.gate_type as string | undefined;
    if (gateType === 'approval') return 'Approbation';
    if (gateType === 'maintenance_window') return 'Fenêtre maintenance';
    const conditions = output?.gate_conditions as Array<{ type?: string }> | undefined;
    if (conditions?.length) {
      const first = conditions[0]?.type;
      if (first === 'approval_granted') return 'Approbation';
      if (first === 'maintenance_window') return 'Fenêtre maintenance';
    }
  }

  return step.step_name;
}

interface TimelineStepItemProps {
  step: ExecutionStepResponse;
  isExpanded: boolean;
  isLast: boolean;
  onToggleExpand: () => void;
  onOpenLogs: () => void;
  /** Story 72.1: correlation_id pour traçabilité. */
  correlationId?: string | null;
}

export function TimelineStepItem({
  step,
  isExpanded,
  isLast,
  onToggleExpand,
  onOpenLogs,
  correlationId,
}: TimelineStepItemProps) {
  const output = step.output as Record<string, unknown> | null | undefined;
  const changeNumber = output?.change_number as string | undefined;
  const changeId = output?.change_id as string | undefined;
  const outputStatus = output?.status as string | undefined;
  const isServiceNow = step.step_type === 'servicenow';
  const showChangeBadge = isServiceNow && changeNumber;
  // Story 57.17: schedule_execution traceability
  const isScheduleExecution = step.step_type === 'schedule_execution';
  const scheduledExecutionId = output?.scheduled_execution_id as number | undefined;
  const scheduledActionName = output?.action_name as string | undefined;
  const scheduledAt = output?.scheduled_at as string | undefined;

  return (
    <div
      role="listitem"
      aria-expanded={isExpanded}
      style={{ display: 'flex', gap: 12, marginBottom: 16 }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: '50%',
            backgroundColor: STATUS_COLOR[step.status],
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            animation: step.status === 'RUNNING' ? 'pulse 1.5s ease-in-out infinite' : undefined,
          }}
        >
          {step.status === 'COMPLETED' && <CheckCircleOutlined style={{ color: '#fff', fontSize: 14 }} />}
          {step.status === 'FAILED' && <CloseCircleOutlined style={{ color: '#fff', fontSize: 14 }} />}
          {step.status === 'SKIPPED' && <MinusOutlined style={{ color: '#fff', fontSize: 14 }} />}
          {step.status === 'RUNNING' && <LoadingOutlined spin style={{ color: '#fff', fontSize: 14 }} />}
          {step.status === 'PENDING' && <ClockCircleOutlined style={{ color: '#fff', fontSize: 14 }} />}
          {step.status === 'WAITING' && <HourglassOutlined style={{ color: '#fff', fontSize: 14 }} />}
        </div>
        {!isLast && (
          <div
            style={{ width: 2, flex: 1, minHeight: 24, backgroundColor: '#E5E7EB', marginTop: 4 }}
          />
        )}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <button
          type="button"
          onClick={onToggleExpand}
          style={{ all: 'unset', cursor: 'pointer', width: '100%', display: 'block', textAlign: 'left' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <Text strong>
              {getStepDisplayName(step)}
            </Text>
            {/* Story 19.1, AC3: "En cours" badge for RUNNING step */}
            {step.status === 'RUNNING' && <Badge status="processing" text="En cours" />}
            {/* Story 58.3, AC4: badge distinct pour WAITING gate */}
            {step.status === 'WAITING' && <Badge status="warning" text="En attente d'approbation" />}
            <Text type="secondary" style={{ fontSize: 12 }}>
              {formatDuration(step.started_at, step.completed_at)}
            </Text>
            {showChangeBadge && (
              <span
                style={{
                  fontSize: 11,
                  padding: '2px 6px',
                  borderRadius: 4,
                  backgroundColor: '#E5E7EB',
                  color: '#374151',
                }}
              >
                Changement {changeNumber}
                {outputStatus === 'pending_approval' && ' — En attente approbation'}
              </span>
            )}
          </div>
        </button>

        {isExpanded && (
          <div
            style={{
              marginTop: 8,
              padding: 12,
              backgroundColor: 'rgba(0,0,0,0.03)',
              borderRadius: 8,
              fontSize: 13,
            }}
          >
            {correlationId && (
              <div style={{ marginBottom: 8, fontSize: 11 }}>
                <Text type="secondary">Correlation ID: </Text>
                <Text copyable={{ text: correlationId }} style={{ fontFamily: 'monospace' }}>
                  {correlationId}
                </Text>
              </div>
            )}
            {step.error_message && (
              <div style={{ color: '#EF4444', marginBottom: 8 }}>{step.error_message}</div>
            )}
            {output && typeof output === 'object' && (
              <FormattedJson value={output} style={{ wordBreak: 'break-word', fontSize: 12 }} />
            )}
            {changeId && (
              <a href={changeId} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12 }}>
                Voir dans ServiceNow
              </a>
            )}
            {/* Story 57.17: Lien vers la planification créée */}
            {isScheduleExecution && scheduledExecutionId != null && step.status === 'COMPLETED' && (
              <div style={{ marginTop: 8 }} data-testid="schedule-execution-badge">
                <span style={{ fontSize: 12, color: '#4f46e5' }}>
                  Exécution planifiée #{scheduledExecutionId}
                  {scheduledActionName && ` — ${scheduledActionName}`}
                  {scheduledAt && ` — ${formatUtcToLocal(scheduledAt)}`}
                </span>
                <div style={{ marginTop: 4 }}>
                  <Link to="/calendar" style={{ fontSize: 12 }} data-testid="link-to-calendar">
                    Voir dans les planifications →
                  </Link>
                </div>
              </div>
            )}
            <div style={{ marginTop: 8 }}>
              <Button type="link" size="small" onClick={onOpenLogs} style={{ padding: 0 }}>
                Voir logs détaillés
              </Button>
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
