/**
 * ParallelGroupTimelineSection — Story 65.6 (AC: #3, #4)
 *
 * Renders a visual grouping for parallel_group sub-steps in the ExecutionTimeline.
 * Displays a group header with an icon and name, an optional "En parallèle" badge
 * when ≥2 sub-steps are RUNNING simultaneously, and the sub-steps indented below.
 */

import React from 'react';
import { Badge } from 'antd';
import { BranchesOutlined } from '@ant-design/icons';
import type { ExecutionStepResponse } from '../../../types/api/executions';
import { TimelineStepItem } from './TimelineStepItem';

interface ParallelGroupTimelineSectionProps {
  groupName: string;
  subSteps: ExecutionStepResponse[];
  expandedId: number | null;
  onToggleExpand: (id: number) => void;
  onOpenLogs: (id: number) => void;
}

export const ParallelGroupTimelineSection: React.FC<ParallelGroupTimelineSectionProps> = ({
  groupName,
  subSteps,
  expandedId,
  onToggleExpand,
  onOpenLogs,
}) => {
  const runningCount = subSteps.filter((s) => s.status === 'RUNNING').length;
  const showParallelBadge = runningCount >= 2;

  return (
    <div data-testid="parallel-group-timeline-section" style={{ marginBottom: 8 }}>
      {/* En-tête groupe */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          padding: '4px 0',
          marginBottom: 4,
          borderBottom: '1px solid var(--ant-color-border-secondary, #f0f0f0)',
        }}
      >
        <BranchesOutlined style={{ color: '#52c41a', fontSize: 14 }} />
        <span style={{ fontWeight: 600, fontSize: 13 }}>
          ⟂ Groupe parallèle — {groupName}
        </span>
        {showParallelBadge && (
          <Badge status="processing" text={`${runningCount} en parallèle`} />
        )}
      </div>

      {/* Sous-steps indentés */}
      <div style={{ paddingLeft: 24 }}>
        {subSteps.map((step, idx) => (
          <TimelineStepItem
            key={step.id}
            step={step}
            isExpanded={expandedId === step.id}
            isLast={idx === subSteps.length - 1}
            onToggleExpand={() => onToggleExpand(step.id)}
            onOpenLogs={() => onOpenLogs(step.id)}
          />
        ))}
      </div>
    </div>
  );
};

export default ParallelGroupTimelineSection;
