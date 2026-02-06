/**
 * WorkflowStepNode — Custom React Flow node for workflow steps (Story 16.5, AC2; Story 16.6).
 *
 * Displays action name, engine/platform icon, retry badge + detailed tooltip,
 * and 3 handles: input (top), success output (bottom-left, green), error output (bottom-right, red).
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Badge, Tooltip, theme } from 'antd';

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
}

const WorkflowStepNode: React.FC<NodeProps> = ({ data, selected }) => {
  const { token } = theme.useToken();
  const nodeData = data as unknown as WorkflowStepNodeData;

  const borderColor =
    nodeData.validationStatus === 'error'
      ? '#ff4d4f'
      : nodeData.validationStatus === 'warning'
        ? '#fa8c16'
        : selected
          ? token.colorPrimary
          : token.colorBorderSecondary;

  const retryTooltipContent = nodeData.retry_enabled ? (
    <div>
      <div>Réessai : {nodeData.retry_max_attempts || 3} tentatives max</div>
      <div>Intervalle : {nodeData.retry_interval_seconds || 60} secondes</div>
      <div>Backoff : {nodeData.retry_backoff_multiplier || 2.0}x</div>
    </div>
  ) : null;

  return (
    <Tooltip title={retryTooltipContent} placement="top">
      <div
        style={{
          border: `2px solid ${borderColor}`,
          borderRadius: 8,
          padding: 12,
          background: token.colorBgContainer,
          minWidth: 200,
          position: 'relative',
          boxShadow: selected ? `0 0 0 2px ${token.colorPrimary}40` : token.boxShadowTertiary,
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

        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>
          {nodeData.name ?? nodeData.action_name}
        </div>
        {nodeData.name && nodeData.name !== nodeData.action_name && (
          <div style={{ fontSize: 11, color: token.colorTextSecondary, marginBottom: 2 }}>
            {nodeData.action_name}
          </div>
        )}
        <div style={{ fontSize: 11, color: token.colorTextTertiary }}>
          {nodeData.action_engine}
          {nodeData.action_platform ? ` / ${nodeData.action_platform}` : ''}
        </div>

        {/* Story 16.6, AC3: Retry badge visible on the node */}
        {nodeData.retry_enabled && (
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
