/**
 * StepDetailDrawer — Detailed view of a single workflow execution step (Story 19.3).
 *
 * Opens as a right-side drawer when clicking on a workflow step node.
 * Displays step metadata header (AC3), timeline/logs (AC2), real-time updates (AC4),
 * and structured error display for FAILED steps (AC9).
 * When step output contains child_execution_id, fetches and shows ExecutionTimeline
 * of the child action instead of raw JSON.
 */

import { useMemo } from 'react';
import { Drawer, Space, Typography, Badge, Alert, Card, Spin, List, theme } from 'antd';
import { CloseOutlined, CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, ClockCircleOutlined, BranchesOutlined } from '@ant-design/icons';
import { StructuredErrorCard } from './StructuredErrorCard';
import { ExecutionTimeline } from './ExecutionTimeline';
import { useChildExecution } from '../../hooks/useChildExecution';
import type { ExecutionStepResponse, WorkflowStep } from '../../types/api';
import { STEP_STATUS_BADGE_CONFIG } from '../../utils/execution-status';
import type { BadgeStatusType } from '../../utils/execution-status';
import { findExecutionStepsForParallelGroup, computeParallelGroupStatus } from '../../utils/parallelGroupUtils';

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

    // Match ExecutionStep by config_step_id (robust), fallback to step_order for legacy
    const executionStep =
      executionSteps.find((es) => es.config_step_id === workflowStep.step_id) ??
      executionSteps.find((es) => es.step_order === workflowStep.order) ??
      null;

    return { workflowStep, executionStep };
  }, [stepId, workflowSteps, executionSteps]);

  // Story 65.6: Compute effective status — aggregated for parallel_group, direct otherwise.
  // Uses config_step_id mapping with legacy fallback to step_name.
  const effectiveStatus = useMemo(() => {
    const wfStep = selectedStep?.workflowStep;
    if (wfStep?.step_type === 'parallel_group') {
      const subSteps =
        wfStep.parallel_steps?.flatMap((stepId) => {
          const byConfig = executionSteps.find((es) => es.config_step_id === stepId);
          if (byConfig) return [byConfig];
          const wf = workflowSteps.find((s) => s.step_id === stepId);
          const byName = wf?.name ? executionSteps.find((es) => es.step_name === wf.name) : undefined;
          return byName ? [byName] : [];
        }) ?? [];
      return computeParallelGroupStatus(subSteps);
    }
    return selectedStep?.executionStep?.status ?? 'PENDING';
  }, [selectedStep, workflowSteps, executionSteps]);

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
    return STEP_STATUS_BADGE_CONFIG[effectiveStatus] ?? { color: 'default', label: effectiveStatus };
  }, [effectiveStatus]);

  const workflowStep = selectedStep?.workflowStep ?? null;
  const executionStep = selectedStep?.executionStep ?? null;
  const stepTitle = workflowStep?.name || workflowStep?.action_name || (workflowStep ? `Étape ${workflowStep.order}` : '');

  // Story 65.6: Detect parallel_group to show sub-steps panel
  const isParallelGroup = workflowStep?.step_type === 'parallel_group';
  const parallelSubSteps = useMemo(() => {
    if (!isParallelGroup || !workflowStep) return [];
    return findExecutionStepsForParallelGroup(workflowStep, workflowSteps, executionSteps);
  }, [isParallelGroup, workflowStep, workflowSteps, executionSteps]);

  // Status icon helper — MUST be before any early return (React hooks rule)
  // Story 65.6: uses effectiveStatus (aggregated for parallel_group) instead of executionStep?.status
  const statusIcon = useMemo(() => {
    if (effectiveStatus === 'COMPLETED') return <CheckCircleOutlined style={{ color: token.colorSuccess, fontSize: 18 }} />;
    if (effectiveStatus === 'FAILED') return <CloseCircleOutlined style={{ color: token.colorError, fontSize: 18 }} />;
    if (effectiveStatus === 'RUNNING') return <LoadingOutlined spin style={{ color: token.colorWarning, fontSize: 18 }} />;
    return <ClockCircleOutlined style={{ color: token.colorTextQuaternary, fontSize: 18 }} />;
  }, [effectiveStatus, token.colorSuccess, token.colorError, token.colorWarning, token.colorTextQuaternary]);

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

  // Story 38.6: DIP — use hook instead of direct service imports
  const {
    childExecution,
    childSteps,
    loading: childLoading,
    error: childError,
  } = useChildExecution(childExecutionId, open);

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
        <Space orientation="vertical" size={8} style={{ width: '100%' }}>
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
        {/* Story 65.6: parallel_group — panneau sous-steps */}
        {isParallelGroup ? (
          <Card
            size="small"
            title={
              <Space size={8}>
                <BranchesOutlined style={{ color: '#52c41a' }} />
                <span>Étapes en parallèle</span>
              </Space>
            }
            data-testid="parallel-group-substeps-panel"
          >
            <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
              {parallelSubSteps.length} étape{parallelSubSteps.length !== 1 ? 's' : ''} en parallèle
            </Typography.Text>
            {parallelSubSteps.length === 0 ? (
              <Typography.Text type="secondary">Aucune sous-étape en cours d'exécution</Typography.Text>
            ) : (
              <List
                size="small"
                dataSource={parallelSubSteps}
                renderItem={(step) => {
                  const cfg = STEP_STATUS_BADGE_CONFIG[step.status] ?? STEP_STATUS_BADGE_CONFIG['PENDING'];
                  const subDuration = step.started_at
                    ? calculateDuration(step.started_at, step.completed_at)
                    : null;
                  return (
                    <List.Item style={{ padding: '8px 0' }}>
                      <Space size={8} style={{ width: '100%' }} align="start">
                        <Badge status={cfg.color as BadgeStatusType} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <Typography.Text strong style={{ display: 'block' }}>
                            {step.step_name}
                          </Typography.Text>
                          <Space size={8}>
                            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                              {step.status === 'RUNNING' ? 'En cours...' : cfg.label}
                            </Typography.Text>
                            {subDuration && (
                              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                {subDuration}
                              </Typography.Text>
                            )}
                          </Space>
                          {step.error_message && step.status === 'FAILED' && (
                            <Typography.Text type="danger" style={{ fontSize: 11, display: 'block' }}>
                              {step.error_message}
                            </Typography.Text>
                          )}
                        </div>
                      </Space>
                    </List.Item>
                  );
                }}
              />
            )}
          </Card>
        ) : !executionStep ? (
          // AC10: Step not yet executed
          <Alert
            type="info"
            showIcon
            title="Étape en attente"
            description="Cette étape n'a pas encore été exécutée. Les détails apparaîtront dès le démarrage."
            data-testid="step-pending-alert"
          />
        ) : (
          <Space orientation="vertical" size={16} style={{ width: '100%' }}>
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
              <Space orientation="vertical" size={4} style={{ width: '100%' }}>
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
                      title="Impossible de charger la timeline de l'action"
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
