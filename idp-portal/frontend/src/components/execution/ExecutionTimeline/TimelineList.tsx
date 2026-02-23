/**
 * TimelineList — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Renders the aria-live region, empty states, and step list.
 */

import { Card, Space, Tag, Typography } from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import { TimelineStepItem } from './TimelineStepItem';
import { formatDuration } from './utils';
import type { ExecutionResponse, ExecutionStepResponse } from '../../../types/api';

const { Text } = Typography;

interface TimelineListProps {
  steps: ExecutionStepResponse[];
  execution: ExecutionResponse | null;
  embedInWorkflowStepDrawer: boolean;
  statusAnnouncement: string;
  expandedId: number | null;
  onToggleExpand: (id: number) => void;
  onOpenLogs: (id: number) => void;
}

export function TimelineList({
  steps,
  execution,
  embedInWorkflowStepDrawer,
  statusAnnouncement,
  expandedId,
  onToggleExpand,
  onOpenLogs,
}: TimelineListProps) {
  return (
    <div role="list" aria-label="Timeline d'exécution" style={{ padding: '16px 0' }}>
      {/* @keyframes pulse — defined once at list level, used by TimelineStepItem for RUNNING steps */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
      {/* Single aria-live region for status announcements (AC4) */}
      <div
        aria-live="polite"
        aria-atomic="true"
        style={{ position: 'absolute', left: '-9999px', width: '1px', height: '1px', overflow: 'hidden' }}
      >
        {statusAnnouncement}
      </div>

      {steps.length === 0 && (
        !embedInWorkflowStepDrawer &&
        execution?.parent_item_type === 'workflow' &&
        execution?.parent_execution_id ? (
          <Card size="small" style={{ maxWidth: 400 }}>
            <Space orientation="vertical" size={8}>
              <Text strong>Action du workflow</Text>
              <Text type="secondary">
                Cette action a été exécutée dans le cadre d'un workflow. Les étapes détaillées sont visibles sur l'exécution parente.
              </Text>
              <Space>
                <Tag color={execution.status === 'COMPLETED' ? 'success' : execution.status === 'FAILED' ? 'error' : 'default'}>
                  {execution.status}
                </Tag>
                {execution.started_at && execution.completed_at && (
                  <Text type="secondary">
                    Durée: {formatDuration(execution.started_at, execution.completed_at)}
                  </Text>
                )}
              </Space>
              <a href={`/executions/${execution.parent_execution_id}`} target="_blank" rel="noopener noreferrer">
                <LinkOutlined /> Voir le workflow parent
              </a>
            </Space>
          </Card>
        ) : (
          <Text type="secondary">Aucune étape à afficher</Text>
        )
      )}

      {steps.map((step, idx) => (
        <TimelineStepItem
          key={step.id || idx}
          step={step}
          isExpanded={expandedId === step.id}
          isLast={idx === steps.length - 1}
          onToggleExpand={() => onToggleExpand(step.id)}
          onOpenLogs={() => onOpenLogs(step.id)}
        />
      ))}
    </div>
  );
}
