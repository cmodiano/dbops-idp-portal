/**
 * StepDetailDrawer — Detailed view of a single workflow execution step (Story 19.3).
 *
 * Opens as a right-side drawer when clicking on a workflow step node.
 * Displays step metadata header (AC3), timeline/logs (AC2), real-time updates (AC4),
 * and structured error display for FAILED steps (AC9).
 * No additional API fetch — uses data already loaded by WorkflowExecutionGraph (AC10).
 */

import { useMemo } from 'react';
import { Drawer, Space, Typography, Badge, Alert } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { ExecutionTimeline } from './ExecutionTimeline';
import { StructuredErrorCard } from './StructuredErrorCard';
import type { ExecutionStepResponse, WorkflowStep } from '../../types/api';

const { Title, Text } = Typography;

/** Status badge config matching ExecutionView pattern. */
const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  PENDING: { color: 'default', label: 'En attente' },
  RUNNING: { color: 'processing', label: 'En cours' },
  COMPLETED: { color: 'success', label: 'Terminé' },
  FAILED: { color: 'error', label: 'Échoué' },
  SKIPPED: { color: 'default', label: 'Ignoré' },
  CANCELLED: { color: 'default', label: 'Annulé' },
};

interface StepDetailDrawerProps {
  open: boolean;
  stepId: string | null;
  executionId: number;
  executionSteps: ExecutionStepResponse[];
  workflowSteps: WorkflowStep[];
  onClose: () => void;
}

/** Calculate human-readable duration between two timestamps or elapsed time. */
function calculateDuration(startedAt: string | null, completedAt: string | null): string | null {
  if (!startedAt) return null;
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const durationSec = Math.floor((end - start) / 1000);
  if (durationSec < 60) return `${durationSec}s`;
  const minutes = Math.floor(durationSec / 60);
  const seconds = durationSec % 60;
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}

export function StepDetailDrawer({
  open,
  stepId,
  executionId,
  executionSteps,
  workflowSteps,
  onClose,
}: StepDetailDrawerProps) {
  // AC10: Find selected step from data already loaded (no fetch)
  const selectedStep = useMemo(() => {
    if (!stepId || !workflowSteps?.length) return null;

    const workflowStep = workflowSteps.find((s) => s.step_id === stepId);
    if (!workflowStep) return null;

    // Match ExecutionStep by step_order
    const executionStep = executionSteps.find(
      (es) => es.step_order === workflowStep.order,
    ) ?? null;

    return { workflowStep, executionStep };
  }, [stepId, workflowSteps, executionSteps]);

  // AC3: Duration
  const duration = useMemo(() => {
    if (!selectedStep?.executionStep) return null;
    return calculateDuration(
      selectedStep.executionStep.started_at,
      selectedStep.executionStep.completed_at,
    );
  }, [selectedStep?.executionStep]);

  // AC3: Status badge
  const statusCfg = useMemo(() => {
    const status = selectedStep?.executionStep?.status ?? 'PENDING';
    return STATUS_CONFIG[status] ?? STATUS_CONFIG.PENDING;
  }, [selectedStep?.executionStep?.status]);

  if (!open || !stepId || !selectedStep) return null;

  const { workflowStep, executionStep } = selectedStep;
  const stepTitle = workflowStep.name || workflowStep.action_name || `Étape ${workflowStep.order}`;

  return (
    <Drawer
      title={null}
      placement="right"
      size="large"
      open={open}
      onClose={onClose}
      closable={false}
      destroyOnClose={false}
      styles={{
        body: { padding: 0 },
        header: { display: 'none' },
        wrapper: { width: '50%' },
      }}
      data-testid="step-detail-drawer"
    >
      {/* AC3: Step metadata header */}
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid #E5E7EB',
          background: '#FAFAFA',
          position: 'sticky',
          top: 0,
          zIndex: 1,
        }}
        data-testid="step-detail-header"
      >
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Title level={4} style={{ margin: 0 }}>{stepTitle}</Title>
            <CloseOutlined
              onClick={onClose}
              style={{ cursor: 'pointer', fontSize: 16 }}
              data-testid="step-detail-close"
              aria-label="Fermer le détail de l'étape"
            />
          </div>

          <Space size={16} wrap>
            <Space size={4}>
              <Text type="secondary">Ordre:</Text>
              <Text strong>#{workflowStep.order}</Text>
            </Space>
            {workflowStep.action_name && (
              <Space size={4}>
                <Text type="secondary">Action:</Text>
                <Text>{workflowStep.action_name}</Text>
              </Space>
            )}
            <Space size={4}>
              <Text type="secondary">Statut:</Text>
              <Badge
                status={statusCfg.color as 'default' | 'processing' | 'success' | 'error' | 'warning'}
                text={statusCfg.label}
              />
            </Space>
            {duration && (
              <Space size={4}>
                <Text type="secondary">Durée:</Text>
                <Text>{duration}</Text>
              </Space>
            )}
          </Space>
        </Space>
      </div>

      {/* Main content */}
      <div style={{ padding: 24 }}>
        {!executionStep ? (
          // AC10: Step not yet executed
          <Alert
            type="info"
            showIcon
            message="Étape en attente"
            description="Cette étape n'a pas encore été exécutée. Les détails apparaîtront dès le démarrage."
            data-testid="step-pending-alert"
          />
        ) : (
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            {/* AC9: Structured error for FAILED step */}
            {executionStep.status === 'FAILED' && (
              <StructuredErrorCard
                quoi={executionStep.step_name}
                pourquoi={executionStep.error_message ?? 'Erreur inconnue'}
                stepId={executionStep.id}
                executionId={executionId}
              />
            )}

            {/* AC2: Timeline and logs for this step */}
            <ExecutionTimeline
              execution={null}
              steps={[executionStep]}
              mode="historical"
            />
          </Space>
        )}
      </div>
    </Drawer>
  );
}
