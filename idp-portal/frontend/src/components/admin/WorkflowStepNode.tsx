/**
 * WorkflowStepNode — Custom React Flow node for workflow steps (Story 16.5, AC2; Story 16.6; Story 16.7).
 *
 * Displays action name, engine/platform icon, retry badge + detailed tooltip
 * with exit paths (success/error), and 3 handles: input (top), success output
 * (bottom-left, green), error output (bottom-right, red).
 */

import React, { memo, useMemo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Badge, Divider, Tooltip, theme } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined, MinusCircleOutlined } from '@ant-design/icons';

export interface WorkflowStepNodeData {
  action_id: number;
  action_name: string;
  action_engine: string;
  action_platform: string;
  name: string | null;
  retry_enabled: boolean;
  retry_max_attempts: number | null;
  retry_interval_seconds: number | null;
  retry_backoff_multiplier: number | null;
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

  /** Story 19.2: Execution status for read-only visualization (optional, backward compatible) */
  executionStatus?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';
  /** Story 19.2: Step execution duration (e.g. "1m 30s") */
  executionDuration?: string | null;
}

const WorkflowStepNode: React.FC<NodeProps> = ({ data, selected }) => {
  const { token } = theme.useToken();
  const nodeData = data as unknown as WorkflowStepNodeData;

  // Execution status colors — subtle, professional palette
  const executionBorderColors: Record<string, string> = {
    RUNNING: '#fa8c16',
    COMPLETED: '#389e0d', // Slightly muted green (ant design green-7)
    FAILED: '#cf1322',    // Slightly muted red (ant design red-7)
    SKIPPED: '#8c8c8c',
    PENDING: token.colorBorderSecondary,
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
  const borderWidth = nodeData.executionStatus === 'RUNNING' ? 2 : 2;
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
    };

    // Story 19.2: Execution mode tooltip (takes priority when executionStatus is present)
    if (nodeData.executionStatus) {
      return (
        <div style={{ fontSize: 12 }}>
          <div style={{ marginBottom: 4, fontWeight: 600 }}>{nodeData.name ?? nodeData.action_name}</div>
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
            <div style={{ marginBottom: 4, fontWeight: 600 }}>{nodeData.name ?? nodeData.action_name}</div>
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
        {/* Retry section (Story 16.6) */}
        {hasRetry && (
          <>
            {hasExitPaths && <Divider style={{ margin: '6px 0' }} />}
            <div>Réessai : {nodeData.retry_max_attempts || 3} tentatives max</div>
            <div>Intervalle : {nodeData.retry_interval_seconds || 60} secondes</div>
            <div>Backoff : {nodeData.retry_backoff_multiplier || 2.0}x</div>
          </>
        )}
      </div>
    );
  }, [nodeData]);

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
          opacity: nodeData.executionStatus === 'SKIPPED' ? 0.6 : nodeData.executionStatus === 'PENDING' ? 0.7 : 1,
          transition: 'border-color 0.3s, box-shadow 0.3s, opacity 0.3s',
        }}
        role="img"
        aria-label={`Étape: ${nodeData.name ?? nodeData.action_name}`}
      >
        <Handle
          type="target"
          position={Position.Top}
          id="input"
          style={{ background: token.colorTextTertiary }}
          aria-label="Entrée"
        />

        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {nodeData.name ?? nodeData.action_name}
        </div>
        {nodeData.name && nodeData.name !== nodeData.action_name && (
          <div style={{ fontSize: 11, color: token.colorTextSecondary, marginBottom: 2, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {nodeData.action_name}
          </div>
        )}
        <div style={{ fontSize: 11, color: token.colorTextTertiary }}>
          {nodeData.action_engine}
          {nodeData.action_platform ? ` / ${nodeData.action_platform}` : ''}
        </div>

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

        {/* Story 16.6, AC3: Retry badge visible on the node */}
        {nodeData.retry_enabled && !nodeData.executionStatus && (
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
