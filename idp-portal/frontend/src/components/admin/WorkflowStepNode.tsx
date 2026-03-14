/**
 * WorkflowStepNode — Custom React Flow node for workflow steps (Story 16.5, AC2; Story 16.6; Story 16.7; Story 57.13).
 *
 * Displays action name, engine/platform icon, retry badge + detailed tooltip
 * with exit paths (success/error), and 3 handles: input (top), success output
 * (bottom-left, green), error output (bottom-right, red).
 *
 * Story 57.13: Added step_type badge with color per type (platform, service_call, evaluation, gate, http_request).
 * Story 57.16: Added schedule_execution step type with schedule_source badge display.
 */

import { memo, useMemo } from 'react';
import type { FC } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Badge, Divider, Tag, Tooltip, theme } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, HourglassOutlined, LoadingOutlined, MinusCircleOutlined } from '@ant-design/icons';
import type { WorkflowStepType, ScheduleStepConfig } from '../../types/api';
import { INTEGRATION_LABELS } from './step-config/serviceCallConstants';

// Story 57.13: Color codes and labels per step type
const STEP_TYPE_COLORS: Record<WorkflowStepType, string> = {
  platform:           '#1677ff',  // bleu Ant Design Primary
  service_call:       '#fa8c16',  // orange
  evaluation:         '#722ed1',  // violet
  gate:               '#faad14',  // ambre/jaune
  http_request:       '#13c2c2',  // cyan
  schedule_execution: '#4f46e5',  // indigo (Story 57.16)
  parallel_group:     '#52c41a',  // vert (deprecated, rétro-compat)
};

const STEP_TYPE_LABELS: Record<WorkflowStepType, string> = {
  platform:           'Exécuter',
  service_call:       'Service',
  evaluation:         'Évaluer',
  gate:               'Attendre',
  http_request:       'HTTP',
  schedule_execution: 'Planifier', // Story 57.16
  parallel_group:     'Parallèle', // deprecated, rétro-compat
};


export interface WorkflowStepNodeData {
  action_id?: number | null;
  action_name?: string;
  action_engine?: string;
  action_platform?: string;
  name: string | null;
  retry_enabled?: boolean;
  retry_max_attempts?: number | null;
  retry_interval_seconds?: number | null;
  retry_backoff_multiplier?: number | null;
  /** Validation error/warning for this node */
  validationStatus?: 'error' | 'warning' | null;
  validationMessage?: string | null;
  /** Exit paths for tooltip (Story 16.7, AC6) */
  on_success_step_id?: string | null;
  on_error_step_id?: string | null;
  /** Step names for tooltip (Story 16.7 code review) */
  on_success_step_name?: string | null;
  on_error_step_name?: string | null;

  /** Visual-only flags (Story 16.7, AC1) */
  isStartNode?: boolean;
  isEndNode?: boolean;

  /** Story 19.2: Execution status for read-only visualization (optional, backward compatible). Story 58.3: WAITING ajouté. */
  executionStatus?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED' | 'WAITING';
  /** Story 19.2: Step execution duration (e.g. "1m 30s") */
  executionDuration?: string | null;

  // Story 57.13: step type and type-specific fields
  step_type?: WorkflowStepType;
  step_id?: string | null;
  integration_type?: string | null;
  operation?: string | null;
  policy_id?: number | null;
  policy_name?: string | null;
  gate_type?: 'maintenance_window' | 'approval' | null;
  on_timeout?: 'FAIL' | 'SKIP' | null;
  context_from?: string[] | null;
  approver_profile_ids?: number[] | null;
  timeout?: string | null;
  url?: string | null;
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | null;
  headers?: Record<string, string> | null;
  request_timeout?: number | null;
  condition?: { environment_in?: string[] } | null;
  input_mapping?: Record<string, unknown> | null;
  output_mapping?: Record<string, string> | null;
  // === schedule_execution ===
  /** Story 57.16: Configuration du step de planification. */
  schedule_config?: ScheduleStepConfig | null;
  // === parallel_group — backward compat fields for executions recorded before Story 67.5 ===
  // NEW-FE-G: Kept intentionally — old DB records may contain these fields.
  // `parallel_group` step_type was replaced by fan-out via on_success_step_ids[] in Story 67.5.
  // These fields must remain to avoid TypeScript errors when displaying historical executions.
  /** Story 65.4: Liste des step_id à exécuter en parallèle (≥2 requis). */
  parallel_steps?: string[] | null;
  /** Story 65.4: Step suivant si tous les sous-steps réussissent. */
  on_all_success_step_id?: string | null;
  /** Story 65.4: Step suivant si au moins un sous-step échoue (fail-fast). */
  on_any_error_step_id?: string | null;
  /** Story 67.4: Join policy for convergence steps. */
  join_policy?: 'all_success' | 'one_success' | 'all_done' | 'all_failed' | 'one_failed' | null;
}

const WorkflowStepNode: FC<NodeProps> = ({ data, selected }) => {
  const { token } = theme.useToken();
  const nodeData = data as unknown as WorkflowStepNodeData;

  const stepType: WorkflowStepType = nodeData.step_type ?? 'platform';

  // Story 57.13: Primary title for non-platform steps
  const primaryTitle = useMemo(() => {
    if (stepType === 'platform') {
      return nodeData.name ?? nodeData.action_name ?? '';
    }
    if (stepType === 'service_call') {
      const integration = nodeData.integration_type
        ? (INTEGRATION_LABELS[nodeData.integration_type] ?? nodeData.integration_type)
        : '?';
      // Story 82.7: OPERATION_LABELS supprimé — affichage du code brut ; migration via capabilities en 82.8
      const op = nodeData.operation ?? '?';
      return nodeData.name ?? `${integration} — ${op}`;
    }
    if (stepType === 'evaluation') {
      return nodeData.name ?? (nodeData.policy_name ? nodeData.policy_name : `Politique #${nodeData.policy_id ?? '?'}`);
    }
    if (stepType === 'gate') {
      if (nodeData.gate_type === 'maintenance_window') return nodeData.name ?? 'Fenêtre maintenance';
      if (nodeData.gate_type === 'approval') return nodeData.name ?? 'Approbation';
      return nodeData.name ?? 'Gate';
    }
    if (stepType === 'http_request') {
      const url = nodeData.url ? nodeData.url.substring(0, 30) : '?';
      return nodeData.name ?? `${nodeData.method ?? '?'} ${url}${(nodeData.url?.length ?? 0) > 30 ? '…' : ''}`;
    }
    if (stepType === 'schedule_execution') {
      return nodeData.name ?? nodeData.action_name ?? 'Planifier une exécution';
    }
    return nodeData.name ?? '';
  }, [stepType, nodeData]);

  // Execution status colors — subtle, professional palette
  const executionBorderColors: Record<string, string> = {
    RUNNING: '#fa8c16',
    COMPLETED: '#389e0d', // Slightly muted green (ant design green-7)
    FAILED: '#cf1322',    // Slightly muted red (ant design red-7)
    SKIPPED: '#8c8c8c',
    PENDING: token.colorBorderSecondary,
    WAITING: '#d46b08',   // Story 58.3: orange foncé — en attente d'approbation (gate)
  };

  const borderColor =
    nodeData.executionStatus && nodeData.executionStatus !== 'PENDING'
      ? executionBorderColors[nodeData.executionStatus] ?? token.colorBorderSecondary
    : nodeData.validationStatus === 'error'
      ? '#ff4d4f'
      : nodeData.validationStatus === 'warning'
        ? '#fa8c16'
        : selected
          ? token.colorPrimary
          : token.colorBorderSecondary;

  // Subtle 2px border for all states, no heavy glow
  const borderWidth = 2;
  const boxShadowNode = nodeData.executionStatus === 'RUNNING'
    ? '0 0 6px #fa8c1640'
    : selected
      ? `0 0 0 2px ${token.colorPrimary}40`
      : token.boxShadowTertiary;

  // Story 16.7, AC6 + Story 19.2, AC10: Extended tooltip with execution info or exit paths
  const tooltipContent = useMemo(() => {
    // Status labels for execution tooltip (Story 19.2, AC10)
    const executionStatusLabels: Record<string, string> = {
      PENDING: 'En attente',
      RUNNING: 'En cours',
      COMPLETED: 'Terminé',
      FAILED: 'Échoué',
      SKIPPED: 'Annulé',
      WAITING: "En attente d'approbation", // Story 58.3
    };

    // Story 19.2: Execution mode tooltip (takes priority when executionStatus is present)
    if (nodeData.executionStatus) {
      return (
        <div style={{ fontSize: 12 }}>
          <div style={{ marginBottom: 4, fontWeight: 600 }}>{primaryTitle}</div>
          <div>Statut: {executionStatusLabels[nodeData.executionStatus] ?? nodeData.executionStatus}</div>
          {nodeData.executionDuration && <div>Durée: {nodeData.executionDuration}</div>}
        </div>
      );
    }

    // Builder mode: exit paths + retry info
    const hasExitPaths = nodeData.on_success_step_id !== undefined;
    const hasRetry = nodeData.retry_enabled;

    if (!hasExitPaths && !hasRetry) return null;

    return (
      <div style={{ fontSize: 12 }}>
        {/* Exit paths section */}
        {hasExitPaths && (
          <>
            <div style={{ marginBottom: 4, fontWeight: 600 }}>{primaryTitle}</div>
            <div>
              <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 4 }} />
              Succès → {nodeData.on_success_step_name || nodeData.on_success_step_id || 'Fin'}
            </div>
            <div>
              <CloseCircleOutlined style={{ color: '#ff4d4f', marginRight: 4 }} />
              Erreur → {nodeData.on_error_step_name || nodeData.on_error_step_id || 'Fin'}
            </div>
          </>
        )}
        {/* Retry section (Story 16.6) — platform only */}
        {hasRetry && stepType === 'platform' && (
          <>
            {hasExitPaths && <Divider style={{ margin: '6px 0' }} />}
            <div>Réessai : {nodeData.retry_max_attempts || 3} tentatives max</div>
            <div>Intervalle : {nodeData.retry_interval_seconds || 60} secondes</div>
            <div>Backoff : {nodeData.retry_backoff_multiplier || 2.0}x</div>
          </>
        )}
      </div>
    );
  }, [nodeData, primaryTitle, stepType]);

  return (
    <Tooltip title={tooltipContent} placement="top">
      <div
        style={{
          border: `${borderWidth}px solid ${borderColor}`,
          borderRadius: 8,
          padding: 12,
          background: token.colorBgContainer,
          minWidth: 200,
          position: 'relative',
          boxShadow: boxShadowNode,
          opacity: nodeData.executionStatus === 'SKIPPED' ? 0.6 : nodeData.executionStatus === 'PENDING' ? 0.7 : 1, // WAITING = 1 (Story 58.3: pleine opacité car en cours d'attente)
          transition: 'border-color 0.3s, box-shadow 0.3s, opacity 0.3s',
        }}
        role="img"
        aria-label={`Étape: ${primaryTitle}`}
      >
        <Handle
          type="target"
          position={Position.Top}
          id="input"
          style={{ background: token.colorTextTertiary }}
          aria-label="Entrée"
        />

        {/* Story 57.13: Step type badge */}
        <Tag
          color={STEP_TYPE_COLORS[stepType]}
          style={{ fontSize: 10, padding: '0 4px', marginBottom: 4, display: 'inline-block', lineHeight: '16px' }}
        >
          {STEP_TYPE_LABELS[stepType]}
        </Tag>

        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {primaryTitle}
        </div>
        {/* Story 57.16: Badge schedule_source pour schedule_execution */}
        {stepType === 'schedule_execution' && nodeData.schedule_config?.schedule_source && (
          <div style={{ fontSize: 11, color: '#4f46e5', marginTop: 2 }}>
            {nodeData.schedule_config.schedule_source === 'parameter' && 'Paramètre utilisateur'}
            {nodeData.schedule_config.schedule_source === 'fixed_offset' && `Offset: ${nodeData.schedule_config.fixed_offset ?? '?'}`}
            {nodeData.schedule_config.schedule_source === 'recurring' && 'Récurrent'}
          </div>
        )}
        {/* Secondary info for platform steps */}
        {stepType === 'platform' && nodeData.name && nodeData.name !== nodeData.action_name && (
          <div style={{ fontSize: 11, color: token.colorTextSecondary, marginBottom: 2, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {nodeData.action_name}
          </div>
        )}
        {stepType === 'platform' && (
          <div style={{ fontSize: 11, color: token.colorTextTertiary }}>
            {nodeData.action_engine}
            {nodeData.action_platform ? ` / ${nodeData.action_platform}` : ''}
          </div>
        )}

        {/* Execution status icon — small, top-right */}
        {nodeData.executionStatus === 'COMPLETED' && (
          <CheckCircleOutlined style={{ position: 'absolute', top: 8, right: 8, color: '#389e0d', fontSize: 13 }} />
        )}
        {nodeData.executionStatus === 'FAILED' && (
          <CloseCircleOutlined style={{ position: 'absolute', top: 8, right: 8, color: '#cf1322', fontSize: 13 }} />
        )}
        {nodeData.executionStatus === 'RUNNING' && (
          <LoadingOutlined spin style={{ position: 'absolute', top: 8, right: 8, color: '#fa8c16', fontSize: 13 }} />
        )}
        {nodeData.executionStatus === 'SKIPPED' && (
          <MinusCircleOutlined style={{ position: 'absolute', top: 8, right: 8, color: '#8c8c8c', fontSize: 13 }} />
        )}
        {nodeData.executionStatus === 'WAITING' && (
          <HourglassOutlined style={{ position: 'absolute', top: 8, right: 8, color: '#d46b08', fontSize: 13 }} />
        )}

        {/* Story 16.6, AC3: Retry badge visible on the node (platform only) */}
        {nodeData.retry_enabled && !nodeData.executionStatus && stepType === 'platform' && (
          <Badge
            count={`Réessai: ${nodeData.retry_max_attempts || 3}×`}
            style={{
              position: 'absolute',
              top: 4,
              right: 4,
              backgroundColor: token.colorPrimary,
              fontSize: 10,
            }}
          />
        )}

        {nodeData.validationMessage && (
          <div
            style={{
              fontSize: 10,
              color: nodeData.validationStatus === 'error' ? '#ff4d4f' : '#fa8c16',
              marginTop: 4,
            }}
            role="alert"
          >
            {nodeData.validationMessage}
          </div>
        )}

        <Handle
          type="source"
          position={Position.Bottom}
          id="success"
          style={{ left: '30%', background: '#52c41a' }}
          aria-label="Sortie succès"
        />
        <Handle
          type="source"
          position={Position.Bottom}
          id="error"
          style={{ left: '70%', background: '#ff4d4f' }}
          aria-label="Sortie erreur"
        />
      </div>
    </Tooltip>
  );
};

export default memo(WorkflowStepNode);
