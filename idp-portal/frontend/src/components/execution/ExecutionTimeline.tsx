/**
 * ExecutionTimeline - Real-time execution timeline (Story 4.6, 4.7; Story 7.4 approval).
 *
 * Story 34.12 (SOLID-FE-1): Refactored into pure orchestrator.
 * Logic extracted to: useExecutionData, useAutoRemediationState, useStepUIState.
 * JSX extracted to: ExecutionStatusBanners, RemediationPanel, TimelineList, StepLogsDrawer.
 */

import { useMemo } from 'react';
import { LoadingOutlined } from '@ant-design/icons';
import { Spin, Typography } from 'antd';
import { useRemediationSuggestions } from '../../hooks/useRemediationSuggestions';
import { useRemediationContext } from '../../hooks/useRemediationContext';
import { useExecutionData } from '../../hooks/useExecutionData';
import { useAutoRemediationState } from '../../hooks/useAutoRemediationState';
import { useStepUIState } from '../../hooks/useStepUIState';
import {
  ExecutionStatusBanners,
  RemediationPanel,
  TimelineList,
  StepLogsDrawer,
} from './ExecutionTimeline/index';
import type { ExecutionResponse, ExecutionStepResponse, RemediationSuggestion } from '../../types/api';

const { Text } = Typography;

export interface ExecutionTimelineProps {
  executionId?: number | null;
  execution?: ExecutionResponse | null;
  steps?: ExecutionStepResponse[];
  mode?: 'realtime' | 'historical';
  /** Callback Relancer (Story 4.7, AC2). */
  onRetry?: () => void;
  /** Callback Contacter DBA (Story 4.7, AC2). */
  onContact?: () => void;
  /** Variant for StructuredErrorCard: 'default' or 'business' (Story 7.2, Task 4.2). */
  errorCardVariant?: 'default' | 'business';
  /** Callback when a remediation suggestion is clicked (Story 9.1, AC1). */
  onSuggestionClick?: (suggestion: RemediationSuggestion) => void;
  /** When true, timeline is shown inside the workflow step drawer (child execution). Do not show "Voir le workflow parent". */
  embedInWorkflowStepDrawer?: boolean;
}

export function ExecutionTimeline({
  executionId,
  execution: executionProp,
  steps: stepsProp,
  mode = 'realtime',
  onRetry,
  onContact,
  errorCardVariant = 'default',
  onSuggestionClick,
  embedInWorkflowStepDrawer = false,
}: ExecutionTimelineProps) {
  const { steps, execution, loading, error, isPolling, useRealtime, lastMessage } = useExecutionData({
    executionId,
    executionProp,
    stepsProp,
    mode,
  });

  const autoRemediationState = useAutoRemediationState(lastMessage, executionId);

  const { expandedId, setExpandedId, logsDrawerStepId, setLogsDrawerStepId, logsDrawerStep, logsDrawerContentRef } =
    useStepUIState(steps);

  const { suggestions: remediationSuggestions, loading: suggestionsLoading } = useRemediationSuggestions(
    executionId ?? null,
    execution?.status ?? null,
  );

  const { context: remediationContext, loading: remediationLoading } = useRemediationContext(
    executionId ?? null,
    execution?.status ?? null,
  );

  const failedStep = useMemo(() => steps.find((s) => s.status === 'FAILED'), [steps]);

  const statusAnnouncement = useMemo(() => {
    const runningStep = steps.find((s) => s.status === 'RUNNING');
    const currentFailedStep = steps.find((s) => s.status === 'FAILED');
    if (currentFailedStep) return `Étape ${currentFailedStep.step_name} a échoué`;
    if (runningStep) return `Étape ${runningStep.step_name} en cours`;
    const completedCount = steps.filter((s) => s.status === 'COMPLETED').length;
    if (completedCount === steps.length && steps.length > 0) return 'Toutes les étapes terminées';
    return '';
  }, [steps]);

  if (useRealtime && loading && steps.length === 0) {
    return (
      <div style={{ padding: 24, textAlign: 'center' }}>
        <Spin indicator={<LoadingOutlined spin />} />
        <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>Chargement...</Text>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24, color: '#EF4444' }}>
        <Text type="danger">{error}</Text>
      </div>
    );
  }

  return (
    <>
      <ExecutionStatusBanners
        execution={execution}
        isPolling={isPolling}
        autoRemediationState={autoRemediationState}
        steps={steps}
      />

      <RemediationPanel
        execution={execution}
        failedStep={failedStep}
        executionId={executionId}
        onRetry={onRetry}
        onContact={onContact}
        onViewLogs={setLogsDrawerStepId}
        errorCardVariant={errorCardVariant}
        remediationSuggestions={remediationSuggestions}
        suggestionsLoading={suggestionsLoading}
        onSuggestionClick={onSuggestionClick}
        remediationContext={remediationContext}
        remediationLoading={remediationLoading}
      />

      <TimelineList
        steps={steps}
        execution={execution}
        embedInWorkflowStepDrawer={embedInWorkflowStepDrawer}
        statusAnnouncement={statusAnnouncement}
        expandedId={expandedId}
        onToggleExpand={(id) => setExpandedId(expandedId === id ? null : id)}
        onOpenLogs={setLogsDrawerStepId}
      />

      <StepLogsDrawer
        step={logsDrawerStep}
        open={logsDrawerStepId != null}
        onClose={() => setLogsDrawerStepId(null)}
        contentRef={logsDrawerContentRef}
      />
    </>
  );
}
