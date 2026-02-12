/**
 * ExecutionTimeline - Real-time execution timeline (Story 4.6, 4.7; Story 7.4 approval).
 *
 * Vertical timeline with nodes per step. States: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED.
 * Story 4.7: Bandeau succès (AC1), StructuredErrorCard (AC2), logs expand + panneau détaillé (AC3, AC4).
 * Story 7.4: PENDING_APPROVAL and REJECTED status display.
 * AC4: role="list", role="listitem", aria-expanded, aria-live="polite".
 */

import { useState, useMemo, useRef, useEffect } from 'react';
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, MinusOutlined, ClockCircleOutlined, LinkOutlined, WarningOutlined, SyncOutlined, ToolOutlined, StopOutlined, ReloadOutlined } from '@ant-design/icons';
import { Spin, Typography, Alert, Drawer, Button, Tooltip, Tag, Card, Space, Skeleton, Badge } from 'antd';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useExecutionPolling } from '../../hooks/useExecutionPolling';
import { useRemediationSuggestions } from '../../hooks/useRemediationSuggestions';
import { useRemediationContext } from '../../hooks/useRemediationContext';
import { StructuredErrorCard } from './StructuredErrorCard';
import type { ExecutionResponse, ExecutionStepResponse, ExecutionStepStatus, RemediationSuggestion, ExecutionStatusType } from '../../types/api';

const FORCE_POLLING = import.meta.env.VITE_SIMULATE_EXECUTION === 'true';

const { Text } = Typography;

const STATUS_COLOR: Record<ExecutionStepStatus, string> = {
  PENDING: '#9CA3AF',
  RUNNING: '#3B82F6',
  COMPLETED: '#10B981',
  FAILED: '#EF4444',
  SKIPPED: '#9CA3AF',
};

function formatDuration(started: string | null, completed: string | null): string {
  if (!started || !completed) return '';
  const a = new Date(started).getTime();
  const b = new Date(completed).getTime();
  const s = Math.round((b - a) / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}

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
}: ExecutionTimelineProps) {
  const useRealtime = mode === 'realtime' && executionId != null;

  // Story 19.0: Use polling instead of WebSocket when VITE_SIMULATE_EXECUTION=true
  const useWs = useRealtime && !FORCE_POLLING;
  const { steps: wsSteps, execution: wsExecution, loading: wsLoading, error: wsError, lastMessage } = useWebSocket(useWs ? executionId : null);

  // Story 19.0: Detect WebSocket failure and fallback to polling (AC8)
  const wsHasError = useWs && wsError != null;
  const usePolling = useRealtime && (FORCE_POLLING || wsHasError);
  const { execution: pollExecution, steps: pollSteps, isPolling, error: pollError } = useExecutionPolling({
    executionId: executionId ?? null,
    enabled: usePolling,
    interval: 2500,
  });

  const loading = useWs ? wsLoading : false;
  const error = useWs && !wsHasError ? wsError : (pollError?.message ?? null);

  // Story 9.3: Listen for auto-remediation WebSocket events
  // Fix: Batch state updates to avoid race conditions during mount
  useEffect(() => {
    if (!lastMessage) return;

    // Use functional updates to ensure state consistency
    if (lastMessage.type === 'auto_remediation_started') {
      const data = lastMessage.data as { child_execution_id?: number; corrective_action_name?: string } | undefined;
      setAutoRemediationState(() => ({
        inProgress: true,
        failed: false,
        childExecutionId: data?.child_execution_id ?? null,
        correctiveActionName: data?.corrective_action_name ?? null,
        failureMessage: null,
      }));
    } else if (lastMessage.type === 'auto_remediation_failed') {
      const data = lastMessage.data as { child_execution_id?: number; message?: string } | undefined;
      setAutoRemediationState((prev) => ({
        ...prev,
        inProgress: false,
        failed: true,
        childExecutionId: data?.child_execution_id ?? prev.childExecutionId,
        failureMessage: data?.message ?? 'Tentative de correction automatique échouée',
      }));
    }
  }, [lastMessage]);

  const steps = useMemo(
    () => {
      if (usePolling) return pollSteps;
      if (useWs) return wsSteps;
      return stepsProp ?? [];
    },
    [usePolling, useWs, pollSteps, wsSteps, stepsProp]
  );
  const execution = usePolling ? pollExecution : (useWs ? wsExecution : executionProp ?? null);

  // Story 9.1, Task 11.1-11.2: Fetch remediation suggestions for failed executions
  const { suggestions: remediationSuggestions, loading: suggestionsLoading } = useRemediationSuggestions(
    executionId ?? null,
    execution?.status ?? null
  );

  // Story 9.2, Task 17: Fetch remediation context for failed executions
  const { context: remediationContext, loading: remediationLoading } = useRemediationContext(
    executionId ?? null,
    execution?.status ?? null
  );

  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [logsDrawerStepId, setLogsDrawerStepId] = useState<number | null>(null);
  const logsDrawerContentRef = useRef<HTMLDivElement>(null);

  // Story 9.3: Track auto-remediation state from WebSocket events
  const [autoRemediationState, setAutoRemediationState] = useState<{
    inProgress: boolean;
    failed: boolean;
    childExecutionId: number | null;
    correctiveActionName: string | null;
    failureMessage: string | null;
  }>({
    inProgress: false,
    failed: false,
    childExecutionId: null,
    correctiveActionName: null,
    failureMessage: null,
  });

  // AC4/Task 4.3: Focus trap — move focus into drawer when it opens
  useEffect(() => {
    if (logsDrawerStepId != null && logsDrawerContentRef.current) {
      logsDrawerContentRef.current.focus();
    }
  }, [logsDrawerStepId]);

  // Story 9.3: Reset auto-remediation state when execution changes (track previous)
  const prevExecutionIdRef = useRef(executionId);
  useEffect(() => {
    if (prevExecutionIdRef.current !== executionId) {
      setAutoRemediationState({
        inProgress: false,
        failed: false,
        childExecutionId: null,
        correctiveActionName: null,
        failureMessage: null,
      });
      prevExecutionIdRef.current = executionId;
    }
  }, [executionId]);

  const failedStep = useMemo(() => steps.find((s) => s.status === 'FAILED'), [steps]);
  const logsDrawerStep = useMemo(
    () => (logsDrawerStepId != null ? steps.find((s) => s.id === logsDrawerStepId) : null),
    [steps, logsDrawerStepId],
  );

  // Dedicated aria-live announcement for status changes (AC4 accessibility)
  const statusAnnouncement = useMemo(() => {
    const runningStep = steps.find((s) => s.status === 'RUNNING');
    const failedStep = steps.find((s) => s.status === 'FAILED');
    if (failedStep) return `Étape ${failedStep.step_name} a échoué`;
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
      {/* Story 19.0, AC8: Polling mode indicator */}
      {isPolling && (
        <Alert
          type="info"
          showIcon
          icon={<ReloadOutlined spin />}
          title="Mode polling activé (dev)"
          closable
          style={{ marginBottom: 16 }}
          data-testid="polling-mode-alert"
        />
      )}

      {/* Story 9.2, Task 18: Alert when this is a remediation (NOT workflow child) */}
      {execution?.parent_execution_id &&
        execution?.parent_item_type !== 'workflow' && (
          <Alert
            type="info"
            showIcon
            icon={<LinkOutlined />}
            title={
              <>
                Cette exécution est une action corrective de l'exécution{' '}
                <a href={`/executions/${execution.parent_execution_id}`}>
                  #{execution.parent_execution_id}
                </a>
              </>
            }
            style={{ marginBottom: 16 }}
            data-testid="parent-execution-alert"
          />
        )}

      {/* Story 7.4 AC1: Bandeau attente approbation */}
      {execution?.status === 'PENDING_APPROVAL' && (
        <Alert
          type="warning"
          showIcon
          icon={<ClockCircleOutlined />}
          title="En attente d'approbation DBA"
          description={
            <>
              Cette exécution nécessite l'approbation d'un DBA avant de pouvoir démarrer.
              <br />
              <Tag color="orange" style={{ marginTop: 8 }}>Environnement : {execution.environment.toUpperCase()}</Tag>
            </>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 7.4 AC4: Bandeau refus */}
      {execution?.status === 'REJECTED' && (
        <Alert
          type="error"
          showIcon
          icon={<StopOutlined />}
          title="Exécution refusée"
          description={
            <>
              Cette exécution a été refusée par un DBA.
              {execution.approval_comment && (
                <>
                  <br />
                  <strong>Motif :</strong> {execution.approval_comment}
                </>
              )}
              {execution.approved_at && (
                <>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Refusé le {new Date(execution.approved_at).toLocaleString()}
                  </Text>
                </>
              )}
            </>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 4.7, AC1: Bandeau succès quand COMPLETED */}
      {execution?.status === 'COMPLETED' && steps.length > 0 && (
        <Alert
          type="success"
          showIcon
          title="Exécution terminée avec succès"
          description={
            <>
              {steps.length} étape{steps.length > 1 ? 's' : ''}
              {execution.started_at && execution.completed_at && (
                <> — Durée : {formatDuration(execution.started_at, execution.completed_at)}</>
              )}
              {' — '}
              <Tooltip title="Bientôt disponible">
                <span style={{ cursor: 'default', color: 'inherit', textDecoration: 'none' }}>Trace d'audit</span>
              </Tooltip>
              {/* Story 7.4: Show approval info if was approved */}
              {execution.approved_by && execution.approved_at && (
                <>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Approuvé le {new Date(execution.approved_at).toLocaleString()}
                    {execution.approval_comment && <> — {execution.approval_comment}</>}
                  </Text>
                </>
              )}
            </>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 9.3, AC3: Alert when auto-remediation failed (fallback to manual) */}
      {autoRemediationState.failed && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          title="Tentative de correction automatique échouée"
          description={
            <>
              {autoRemediationState.failureMessage || "Le système n'a pas pu corriger automatiquement l'erreur."}
              {' '}Veuillez évaluer manuellement les suggestions ci-dessous.
              {autoRemediationState.childExecutionId && (
                <>
                  <br />
                  <a
                    href={`/executions/${autoRemediationState.childExecutionId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 12 }}
                  >
                    Voir l'exécution corrective →
                  </a>
                </>
              )}
            </>
          }
          closable
          style={{ marginBottom: 16 }}
          data-testid="auto-remediation-failed-alert"
        />
      )}

      {/* Story 9.3, AC2: Auto-remediation in progress node */}
      {autoRemediationState.inProgress && (
        <Card
          style={{ marginBottom: 16, borderColor: '#1890ff' }}
          title={
            <Space>
              <SyncOutlined spin style={{ color: '#1890ff' }} />
              <span>Auto-remédiation en cours</span>
              <Tag color="blue">AUTOMATIQUE</Tag>
            </Space>
          }
          data-testid="auto-remediation-progress-card"
        >
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text>
              <ToolOutlined style={{ marginRight: 8 }} />
              {autoRemediationState.correctiveActionName || 'Action corrective'}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Le système tente de corriger automatiquement l'erreur détectée...
            </Text>
            {autoRemediationState.childExecutionId && (
              <a
                href={`/executions/${autoRemediationState.childExecutionId}`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 12 }}
              >
                Voir exécution corrective →
              </a>
            )}
          </Space>
        </Card>
      )}

      {/* Story 4.7, AC2: StructuredErrorCard quand FAILED; Story 7.2, Task 4.2: pass variant; Story 9.1, Task 11.3-11.5: pass remediation suggestions */}
      {execution?.status === 'FAILED' && failedStep && (
        <div style={{ marginBottom: 16 }}>
          <StructuredErrorCard
            quoi={failedStep.step_name}
            pourquoi={failedStep.error_message ?? 'Erreur inconnue'}
            stepId={failedStep.id}
            executionId={executionId ?? undefined}
            onRetry={onRetry}
            onViewLogs={() => setLogsDrawerStepId(failedStep.id)}
            onContact={onContact}
            variant={errorCardVariant}
            remediationSuggestions={remediationSuggestions ?? undefined}
            suggestionsLoading={suggestionsLoading}
            onSuggestionClick={onSuggestionClick}
          />
        </div>
      )}

      {/* Story 9.2 code-review fix: Show loading skeleton while fetching remediation context */}
      {execution?.status === 'FAILED' && remediationLoading && (
        <Card style={{ marginBottom: 16 }} title="Chargement du contexte de remédiation...">
          <Skeleton active />
        </Card>
      )}

      {/* Story 9.2, Task 17: Display remediation context section for failed executions */}
      {execution?.status === 'FAILED' && !remediationLoading && remediationContext?.has_remediation && (
        <Card
          style={{ marginBottom: 16 }}
          title={
            <Space>
              {remediationContext.successful_remediation ? (
                <>
                  <CheckCircleOutlined style={{ color: '#10B981' }} />
                  <span>Actions correctives appliquées</span>
                  <Tag color="success">Corrigé</Tag>
                </>
              ) : (
                <>
                  <WarningOutlined style={{ color: '#F59E0B' }} />
                  <span>Tentatives de correction</span>
                  <Tag color="warning">Échec</Tag>
                </>
              )}
            </Space>
          }
          data-testid="remediation-context-card"
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            {remediationContext.remediation_actions.map((action) => (
              <Card.Grid
                key={action.execution_id}
                style={{ width: '100%', padding: 12 }}
                hoverable={false}
              >
                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                  <Space>
                    <Tag
                      color={
                        action.status === 'COMPLETED'
                          ? 'success'
                          : action.status === 'FAILED'
                          ? 'error'
                          : action.status === 'RUNNING'
                          ? 'processing'
                          : 'default'
                      }
                    >
                      {action.status}
                    </Tag>
                    <Text strong>{action.action_name}</Text>
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Démarrée: {new Date(action.created_at).toLocaleString()}
                    {action.completed_at && (
                      <> — Terminée: {new Date(action.completed_at).toLocaleString()}</>
                    )}
                  </Text>
                  <a
                    href={`/executions/${action.execution_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 12 }}
                  >
                    Voir exécution →
                  </a>
                </Space>
              </Card.Grid>
            ))}
          </Space>
        </Card>
      )}

      <div
        role="list"
        aria-label="Timeline d'exécution"
        style={{ padding: '16px 0' }}
      >
        {/* Single aria-live region for status announcements (AC4) */}
        <div
          aria-live="polite"
          aria-atomic="true"
          style={{ position: 'absolute', left: '-9999px', width: '1px', height: '1px', overflow: 'hidden' }}
        >
          {statusAnnouncement}
        </div>
        {steps.length === 0 && (
          execution?.parent_item_type === 'workflow' && execution?.parent_execution_id ? (
            <Card size="small" style={{ maxWidth: 400 }}>
              <Space direction="vertical" size={8}>
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
        const isExpanded = expandedId === step.id;
        const output = step.output as Record<string, unknown> | null | undefined;
        const changeNumber = output?.change_number as string | undefined;
        const changeId = output?.change_id as string | undefined;
        const outputStatus = output?.status as string | undefined;
        const isServiceNow = step.step_type === 'servicenow';
        const showChangeBadge = isServiceNow && changeNumber;

        return (
          <div
            key={step.id || idx}
            role="listitem"
            aria-expanded={isExpanded}
            style={{
              display: 'flex',
              gap: 12,
              marginBottom: 16,
            }}
          >
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                flexShrink: 0,
              }}
            >
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
              </div>
              {idx < steps.length - 1 && (
                <div
                  style={{
                    width: 2,
                    flex: 1,
                    minHeight: 24,
                    backgroundColor: '#E5E7EB',
                    marginTop: 4,
                  }}
                />
              )}
            </div>

            <div style={{ flex: 1, minWidth: 0 }}>
              <button
                type="button"
                onClick={() => setExpandedId(isExpanded ? null : step.id)}
                style={{
                  all: 'unset',
                  cursor: 'pointer',
                  width: '100%',
                  display: 'block',
                  textAlign: 'left',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <Text strong>{step.step_name}</Text>
                  {/* Story 19.1, AC3: "En cours" badge for RUNNING step */}
                  {step.status === 'RUNNING' && (
                    <Badge status="processing" text="En cours" />
                  )}
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {formatDuration(step.started_at, step.completed_at) || (
                      step.status === 'RUNNING' ? '' : ''
                    )}
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
                  {step.error_message && (
                    <div style={{ color: '#EF4444', marginBottom: 8 }}>{step.error_message}</div>
                  )}
                  {output && typeof output === 'object' && (
                    <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 12 }}>
                      {JSON.stringify(output, null, 2)}
                    </pre>
                  )}
                  {changeId && (
                    <a href={changeId} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12 }}>
                      Voir dans ServiceNow
                    </a>
                  )}
                  <div style={{ marginTop: 8 }}>
                    <Button
                      type="link"
                      size="small"
                      onClick={() => setLogsDrawerStepId(step.id)}
                      style={{ padding: 0 }}
                    >
                      Voir logs détaillés
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}

        <style>{`
          @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
          }
        `}</style>
      </div>

      {/* Story 4.7, AC4: Panneau logs détaillés — focus trap when open (Task 4.3) */}
      <Drawer
        title={logsDrawerStep ? `Logs détaillés - ${logsDrawerStep.step_name}` : 'Logs détaillés'}
        open={logsDrawerStepId != null}
        onClose={() => setLogsDrawerStepId(null)}
        styles={{ wrapper: { width: 480 } }}
        destroyOnHidden
        aria-label="Logs détaillés de l'étape"
      >
        {logsDrawerStep && (
          <div
            ref={logsDrawerContentRef}
            tabIndex={-1}
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          >
            {logsDrawerStep.started_at && (
              <p style={{ marginBottom: 8 }}>
                <strong>Début :</strong> {new Date(logsDrawerStep.started_at).toLocaleString()}
              </p>
            )}
            {logsDrawerStep.completed_at && (
              <p style={{ marginBottom: 12 }}>
                <strong>Fin :</strong> {new Date(logsDrawerStep.completed_at).toLocaleString()}
              </p>
            )}
            {logsDrawerStep.error_message && (
              <div style={{ color: '#EF4444', marginBottom: 12 }}>
                <strong>Erreur :</strong>
                <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: '4px 0 0 0' }}>
                  {logsDrawerStep.error_message}
                </pre>
              </div>
            )}
            {logsDrawerStep.output != null && typeof logsDrawerStep.output === 'object' && (
              <div>
                <strong>Output :</strong>
                <pre
                  style={{
                    margin: '4px 0 0 0',
                    padding: 12,
                    backgroundColor: 'rgba(0,0,0,0.04)',
                    borderRadius: 4,
                    overflow: 'auto',
                    maxHeight: 400,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(logsDrawerStep.output, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </>
  );
}
