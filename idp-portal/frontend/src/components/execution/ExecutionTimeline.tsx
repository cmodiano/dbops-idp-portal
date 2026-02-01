/**
 * ExecutionTimeline - Real-time execution timeline (Story 4.6, 4.7).
 *
 * Vertical timeline with nodes per step. States: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED.
 * Story 4.7: Bandeau succès (AC1), StructuredErrorCard (AC2), logs expand + panneau détaillé (AC3, AC4).
 * AC4: role="list", role="listitem", aria-expanded, aria-live="polite".
 */

import { useState, useMemo, useRef, useEffect } from 'react';
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, MinusOutlined } from '@ant-design/icons';
import { Spin, Typography, Alert, Drawer, Button, Tooltip } from 'antd';
import { useWebSocket } from '../../hooks/useWebSocket';
import { StructuredErrorCard } from './StructuredErrorCard';
import type { ExecutionResponse, ExecutionStepResponse, ExecutionStepStatus } from '../../types/api';

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
}

export function ExecutionTimeline({
  executionId,
  execution: executionProp,
  steps: stepsProp,
  mode = 'realtime',
  onRetry,
  onContact,
}: ExecutionTimelineProps) {
  const useRealtime = mode === 'realtime' && executionId != null;
  const { steps: wsSteps, execution: wsExecution, loading, error } = useWebSocket(useRealtime ? executionId : null);

  const steps = useMemo(
    () => (useRealtime ? wsSteps : (stepsProp ?? [])),
    [useRealtime, wsSteps, stepsProp]
  );
  const execution = useRealtime ? wsExecution : executionProp ?? null;
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [logsDrawerStepId, setLogsDrawerStepId] = useState<number | null>(null);
  const logsDrawerContentRef = useRef<HTMLDivElement>(null);

  // AC4/Task 4.3: Focus trap — move focus into drawer when it opens
  useEffect(() => {
    if (logsDrawerStepId != null && logsDrawerContentRef.current) {
      logsDrawerContentRef.current.focus();
    }
  }, [logsDrawerStepId]);

  const failedStep = useMemo(() => steps.find((s) => s.status === 'FAILED'), [steps]);
  const logsDrawerStep = useMemo(
    () => (logsDrawerStepId != null ? steps.find((s) => s.id === logsDrawerStepId) : null),
    [steps, logsDrawerStepId],
  );

  // MEDIUM-3 FIX: Dedicated aria-live announcement for status changes
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
            </>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Story 4.7, AC2: StructuredErrorCard quand FAILED */}
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
          />
        </div>
      )}

      <div
        role="list"
        aria-label="Timeline d'exécution"
        style={{ padding: '16px 0' }}
      >
        {/* MEDIUM-3 FIX: Single aria-live region for status announcements (AC4) */}
        <div
          aria-live="polite"
          aria-atomic="true"
          style={{ position: 'absolute', left: '-9999px', width: '1px', height: '1px', overflow: 'hidden' }}
        >
          {statusAnnouncement}
        </div>
        {steps.length === 0 && (
          <Text type="secondary">Aucune étape à afficher</Text>
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
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {formatDuration(step.started_at, step.completed_at) || (
                      step.status === 'RUNNING' ? 'En cours...' : ''
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
