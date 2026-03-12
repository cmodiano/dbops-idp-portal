/**
 * TimelineList — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Renders the aria-live region, empty states, and step list.
 *
 * Story 65.6: Added workflowSteps prop for parallel_group visual grouping (AC: #3, #6).
 */

import { Card, Space, Tag, Typography } from 'antd';
import './TimelineList.css';
import { LinkOutlined } from '@ant-design/icons';
import { TimelineStepItem } from './TimelineStepItem';
import { ParallelGroupTimelineSection } from './ParallelGroupTimelineSection';
import { formatDuration } from './utils';
import {
  buildParallelGroupMap,
  getStepNamesInParallelGroups,
} from '../../../utils/parallelGroupUtils';
import type { ExecutionResponse, ExecutionStepResponse } from '../../../types/api';
import type { WorkflowStep } from '../../../types/api/catalog';

const { Text } = Typography;

interface TimelineListProps {
  steps: ExecutionStepResponse[];
  execution: ExecutionResponse | null;
  embedInWorkflowStepDrawer: boolean;
  statusAnnouncement: string;
  expandedId: number | null;
  onToggleExpand: (id: number) => void;
  onOpenLogs: (id: number) => void;
  /** Story 65.6: workflow steps for parallel_group grouping (optional, AC: #3, #6). */
  workflowSteps?: WorkflowStep[];
  /** Story 72.1: correlation_id pour traçabilité (affiché dans chaque step). */
  correlationId?: string | null;
}

export function TimelineList({
  steps,
  execution,
  embedInWorkflowStepDrawer,
  statusAnnouncement,
  expandedId,
  onToggleExpand,
  onOpenLogs,
  workflowSteps,
  correlationId,
}: TimelineListProps) {
  // Story 65.6: Build parallel group data structures when workflowSteps is available.
  // Fallback (AC: #6): if workflowSteps absent or empty, render classically without grouping.
  const parallelGroupMap =
    workflowSteps?.length
      ? buildParallelGroupMap(workflowSteps, steps)
      : new Map<string, ReturnType<typeof buildParallelGroupMap> extends Map<string, infer V> ? V : never>();

  const stepsInGroups =
    workflowSteps?.length ? getStepNamesInParallelGroups(workflowSteps) : new Set<string>();

  // Map: step_id (config) or step_name (legacy) → group step_id
  const stepIdToGroupId = new Map<string, string>();
  const stepNameToGroupId = new Map<string, string>();
  if (workflowSteps?.length) {
    for (const [groupId, { groupStep }] of parallelGroupMap) {
      for (const subStepId of groupStep.parallel_steps ?? []) {
        stepIdToGroupId.set(subStepId, groupId);
        const subStep = workflowSteps.find((s) => s.step_id === subStepId);
        if (subStep?.name) stepNameToGroupId.set(subStep.name, groupId);
      }
    }
  }

  // Track already-rendered groups to skip duplicate rendering
  const renderedGroups = new Set<string>();

  return (
    <div role="list" aria-label="Timeline d'exécution" style={{ padding: '16px 0' }}>
      {/* @keyframes pulse — defined in TimelineList.css, used by TimelineStepItem for RUNNING steps */}
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

      {steps.map((step, idx) => {
        // Story 65.6: parallel group grouping — prefer config_step_id, fallback to step_name
        const isInGroup =
          (step.config_step_id && stepsInGroups.has(step.config_step_id)) ||
          stepsInGroups.has(step.step_name);
        if (isInGroup) {
          const groupId =
            (step.config_step_id && stepIdToGroupId.get(step.config_step_id)) ??
            stepNameToGroupId.get(step.step_name);
          if (groupId) {
            if (renderedGroups.has(groupId)) {
              // Already rendered as part of the group section — skip
              return null;
            }
            // First step of this group — render the full group section
            renderedGroups.add(groupId);
            const groupInfo = parallelGroupMap.get(groupId);
            if (groupInfo) {
              return (
                <ParallelGroupTimelineSection
                  key={`pg-${groupId}`}
                  groupName={groupInfo.groupStep.name ?? 'Groupe parallèle'}
                  subSteps={groupInfo.subSteps}
                  expandedId={expandedId}
                  onToggleExpand={onToggleExpand}
                  onOpenLogs={onOpenLogs}
                  correlationId={correlationId}
                />
              );
            }
          }
        }

        // Regular step (not part of any group, or workflowSteps not available)
        return (
          <TimelineStepItem
            key={step.id || idx}
            step={step}
            isExpanded={expandedId === step.id}
            isLast={idx === steps.length - 1}
            onToggleExpand={() => onToggleExpand(step.id)}
            onOpenLogs={() => onOpenLogs(step.id)}
            correlationId={correlationId}
          />
        );
      })}
    </div>
  );
}
