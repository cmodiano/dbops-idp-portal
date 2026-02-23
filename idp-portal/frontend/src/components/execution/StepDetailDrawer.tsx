/**
 * StepDetailDrawer — Detailed view of a single workflow execution step (Story 19.3).
 *
 * Opens as a right-side drawer when clicking on a workflow step node.
 * Displays step metadata header (AC3), timeline/logs (AC2), real-time updates (AC4),
 * and structured error display for FAILED steps (AC9).
 * When step output contains child_execution_id, fetches and shows ExecutionTimeline
 * of the child action instead of raw JSON.
 */

import { useMemo, useState, useEffect } from 'react';
import { Drawer, Space, Typography, Badge, Alert, Card, Spin, theme } from 'antd';
import { CloseOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { StructuredErrorCard } from './StructuredErrorCard';
import { ExecutionTimeline } from './ExecutionTimeline';
import { getExecution, getExecutionSteps } from '../../services/execution_service';
import type { ExecutionStepResponse, WorkflowStep, ExecutionResponse } from '../../types/api';
import { STEP_STATUS_BADGE_CONFIG } from '../../utils/execution-status';

const { Title, Text } = Typography;

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
  const { token } = theme.useToken();

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
    return STEP_STATUS_BADGE_CONFIG[status] ?? { color: 'default', label: status };
  }, [selectedStep?.executionStep?.status]);

  const workflowStep = selectedStep?.workflowStep ?? null;
  const executionStep = selectedStep?.executionStep ?? null;
  const stepTitle = workflowStep?.name || workflowStep?.action_name || (workflowStep ? `Étape ${workflowStep.order}` : '');

  // Status icon helper — MUST be before any early return (React hooks rule)
  const statusIcon = useMemo(() => {
    const status = executionStep?.status;
    if (status === 'COMPLETED') return <CheckCircleOutlined style={{ color: token.colorSuccess, fontSize: 18 }} />;
    if (status === 'FAILED') return <CloseCircleOutlined style={{ color: token.colorError, fontSize: 18 }} />;
    if (status === 'RUNNING') return <LoadingOutlined spin style={{ color: token.colorWarning, fontSize: 18 }} />;
    return <ClockCircleOutlined style={{ color: token.colorTextQuaternary, fontSize: 18 }} />;
  }, [executionStep?.status]);

  // Parse step output (logs) — raw JSON for fallback or when no child execution
  const stepLogs = useMemo(() => {
    if (!executionStep?.output) return null;
    if (typeof executionStep.output === 'string') return executionStep.output;
    if (typeof executionStep.output === 'object') {
      return JSON.stringify(executionStep.output, null, 2);
    }
    return null;
  }, [executionStep?.output]);

  // child_execution_id from step output — when present, show timeline of the child action
  const childExecutionId = useMemo(() => {
    if (!executionStep?.output || typeof executionStep.output !== 'object') return null;
    const out = executionStep.output as { child_execution_id?: number };
    const id = out?.child_execution_id;
    return typeof id === 'number' && Number.isFinite(id) ? id : null;
  }, [executionStep?.output]);

  // Fetch child execution + steps when step has child_execution_id
  const [childExecution, setChildExecution] = useState<ExecutionResponse | null>(null);
  const [childSteps, setChildSteps] = useState<ExecutionStepResponse[]>([]);
  const [childLoading, setChildLoading] = useState(false);
  const [childError, setChildError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || childExecutionId == null) {
      setChildExecution(null);
      setChildSteps([]);
      setChildError(null);
      return;
    }
    let cancelled = false;
    setChildLoading(true);
    setChildError(null);
    Promise.all([getExecution(childExecutionId), getExecutionSteps(childExecutionId)])
      .then(([exec, steps]) => {
        if (!cancelled) {
          setChildExecution(exec);
          setChildSteps(steps);
          setChildLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setChildError(err instanceof Error ? err.message : 'Erreur de chargement');
          setChildExecution(null);
          setChildSteps([]);
          setChildLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, childExecutionId]);

  const showChildTimeline = childExecutionId != null && childExecution != null && !childError;

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
      {/* AC3: Step metadata header — uses theme tokens (Story 30.11 AC1) */}
      <div
        style={{
          padding: '16px 24px',
          borderBottom: `1px solid ${token.colorBorder}`,
          background: token.colorBgContainer,
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
              <Title level={4} style={{ margin: 0, color: token.colorText }}>{stepTitle}</Title>
            </Space>
            <CloseOutlined
              onClick={onClose}
              style={{ cursor: 'pointer', fontSize: 16, color: token.colorTextTertiary }}
              data-testid="step-detail-close"
              aria-label="Fermer le détail de l'étape"
            />
          </div>

          <Space size={16} wrap>
            <Space size={4}>
              <Text style={{ color: token.colorTextSecondary }}>Ordre:</Text>
              <Text strong style={{ color: token.colorText }}>#{workflowStep.order}</Text>
            </Space>
            {workflowStep.action_name && (
              <Space size={4}>
                <Text style={{ color: token.colorTextSecondary }}>Action:</Text>
                <Text style={{ color: token.colorText }}>{workflowStep.action_name}</Text>
              </Space>
            )}
            <Space size={4}>
              <Text style={{ color: token.colorTextSecondary }}>Statut:</Text>
              <Badge
                status={statusCfg.color}
                text={<span style={{ color: token.colorText }}>{statusCfg.label}</span>}
              />
            </Space>
            {duration && (
              <Space size={4}>
                <Text style={{ color: token.colorTextSecondary }}>Durée:</Text>
                <Text style={{ color: token.colorText }}>{duration}</Text>
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

            {/* Timeline de l'action enfant (quand step output a child_execution_id) */}
            {childExecutionId != null && (
              <Card size="small" title={<span style={{ fontSize: 13 }}>Timeline de l'action</span>}>
                {childLoading && (
                  <div style={{ padding: 24, textAlign: 'center' }}>
                    <Spin tip="Chargement de l'exécution..." />
                  </div>
                )}
                {childError && (
                  <>
                    <Alert
                      type="warning"
                      showIcon
                      message="Impossible de charger la timeline de l'action"
                      description={childError}
                      style={{ marginBottom: 12 }}
                    />
                    {stepLogs && (
                      <pre
                        style={{
                          margin: 0,
                          padding: 12,
                          background: token.colorBgElevated,
                          color: token.colorText,
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
                    )}
                  </>
                )}
                {showChildTimeline && childExecution && (
                  <>
                    <ExecutionTimeline
                      execution={childExecution}
                      steps={childSteps}
                      mode="historical"
                      embedInWorkflowStepDrawer
                    />
                    {childSteps.length === 0 && stepLogs && (
                      <Card size="small" title={<span style={{ fontSize: 13 }}>Résumé de l&apos;étape (output)</span>} style={{ marginTop: 16 }}>
                        <pre
                          style={{
                            margin: 0,
                            padding: 12,
                            background: token.colorBgElevated,
                            color: token.colorText,
                            borderRadius: 6,
                            fontSize: 12,
                            fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
                            lineHeight: 1.6,
                            overflowX: 'auto',
                            maxHeight: 300,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                          }}
                        >
                          {stepLogs}
                        </pre>
                      </Card>
                    )}
                  </>
                )}
              </Card>
            )}

            {/* Logs (JSON) — when no child execution or as fallback */}
            {stepLogs && childExecutionId == null && (
              <Card size="small" title={<span style={{ fontSize: 13 }}>Logs</span>}>
                <pre
                  style={{
                    margin: 0,
                    padding: 12,
                    background: token.colorBgElevated,
                    color: token.colorText,
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
              <Card size="small" title={<span style={{ fontSize: 13, color: token.colorError }}>Message d'erreur</span>}>
                <Text type="danger">{executionStep.error_message}</Text>
              </Card>
            )}
          </Space>
        )}
      </div>
    </Drawer>
  );
}
