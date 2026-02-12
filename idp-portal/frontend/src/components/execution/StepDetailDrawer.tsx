/**
 * StepDetailDrawer — Detailed view of a single workflow execution step (Story 19.3).
 *
 * Opens as a right-side drawer when clicking on a workflow step node.
 * Displays step metadata header (AC3), timeline/logs (AC2), real-time updates (AC4),
 * and structured error display for FAILED steps (AC9).
 * No additional API fetch — uses data already loaded by WorkflowExecutionGraph (AC10).
 */

import { useMemo } from 'react';
import { Drawer, Space, Typography, Badge, Alert, Card } from 'antd';
import { CloseOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ClockCircleOutlined } from '@ant-design/icons';
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

  const workflowStep = selectedStep?.workflowStep ?? null;
  const executionStep = selectedStep?.executionStep ?? null;
  const stepTitle = workflowStep?.name || workflowStep?.action_name || (workflowStep ? `Étape ${workflowStep.order}` : '');

  // Status icon helper — MUST be before any early return (React hooks rule)
  const statusIcon = useMemo(() => {
    const status = executionStep?.status;
    if (status === 'COMPLETED') return <CheckCircleOutlined style={{ color: '#389e0d', fontSize: 18 }} />;
    if (status === 'FAILED') return <CloseCircleOutlined style={{ color: '#cf1322', fontSize: 18 }} />;
    if (status === 'RUNNING') return <LoadingOutlined spin style={{ color: '#fa8c16', fontSize: 18 }} />;
    return <ClockCircleOutlined style={{ color: '#8c8c8c', fontSize: 18 }} />;
  }, [executionStep?.status]);

  // Parse step output (logs)
  const stepLogs = useMemo(() => {
    if (!executionStep?.output) return null;
    if (typeof executionStep.output === 'string') return executionStep.output;
    if (typeof executionStep.output === 'object') {
      return JSON.stringify(executionStep.output, null, 2);
    }
    return null;
  }, [executionStep?.output]);

  // Early return AFTER all hooks
  if (!open || !stepId || !selectedStep || !workflowStep) return null;

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
      {/* AC3: Step metadata header — uses theme-safe colors */}
      <div
        style={{
          padding: '16px 24px',
          borderBottom: '1px solid #303030',
          background: '#1f1f1f',
          position: 'sticky',
          top: 0,
          zIndex: 1,
        }}
        data-testid="step-detail-header"
      >
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Space size={8} align="center">
              {statusIcon}
              <Title level={4} style={{ margin: 0, color: '#e8e8e8' }}>{stepTitle}</Title>
            </Space>
            <CloseOutlined
              onClick={onClose}
              style={{ cursor: 'pointer', fontSize: 16, color: '#999' }}
              data-testid="step-detail-close"
              aria-label="Fermer le détail de l'étape"
            />
          </div>

          <Space size={16} wrap>
            <Space size={4}>
              <Text style={{ color: '#999' }}>Ordre:</Text>
              <Text strong style={{ color: '#e8e8e8' }}>#{workflowStep.order}</Text>
            </Space>
            {workflowStep.action_name && (
              <Space size={4}>
                <Text style={{ color: '#999' }}>Action:</Text>
                <Text style={{ color: '#e8e8e8' }}>{workflowStep.action_name}</Text>
              </Space>
            )}
            <Space size={4}>
              <Text style={{ color: '#999' }}>Statut:</Text>
              <Badge
                status={statusCfg.color as 'default' | 'processing' | 'success' | 'error' | 'warning'}
                text={<span style={{ color: '#e8e8e8' }}>{statusCfg.label}</span>}
              />
            </Space>
            {duration && (
              <Space size={4}>
                <Text style={{ color: '#999' }}>Durée:</Text>
                <Text style={{ color: '#e8e8e8' }}>{duration}</Text>
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

            {/* Step info card */}
            <Card size="small" title={<span style={{ fontSize: 13 }}>{executionStep.step_name}</span>}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space size={8}>
                  {statusIcon}
                  <Text strong>{statusCfg.label}</Text>
                  {duration && <Text type="secondary">({duration})</Text>}
                </Space>
                {executionStep.started_at && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Démarré: {new Date(executionStep.started_at).toLocaleString()}
                  </Text>
                )}
                {executionStep.completed_at && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Terminé: {new Date(executionStep.completed_at).toLocaleString()}
                  </Text>
                )}
                {executionStep.platform_job_id && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Job ID: {executionStep.platform_job_id}
                  </Text>
                )}
              </Space>
            </Card>

            {/* Logs — shown by default, no need to click */}
            {stepLogs && (
              <Card size="small" title={<span style={{ fontSize: 13 }}>Logs</span>}>
                <pre
                  style={{
                    margin: 0,
                    padding: 12,
                    background: '#141414',
                    color: '#d4d4d4',
                    borderRadius: 6,
                    fontSize: 12,
                    fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
                    lineHeight: 1.6,
                    overflowX: 'auto',
                    maxHeight: 400,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {stepLogs}
                </pre>
              </Card>
            )}

            {executionStep.error_message && (
              <Card size="small" title={<span style={{ fontSize: 13, color: '#ff4d4f' }}>Message d'erreur</span>}>
                <Text type="danger">{executionStep.error_message}</Text>
              </Card>
            )}
          </Space>
        )}
      </div>
    </Drawer>
  );
}
