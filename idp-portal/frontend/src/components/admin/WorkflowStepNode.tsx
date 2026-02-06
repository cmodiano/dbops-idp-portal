/**
 * WorkflowStepNode — Custom React Flow node for workflow steps (Story 16.5, AC2).
 *
 * Displays action name, engine/platform icon, retry indicator,
 * and 3 handles: input (top), success output (bottom-left, green), error output (bottom-right, red).
 */

import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Tooltip, theme } from 'antd';
import { RetweetOutlined } from '@ant-design/icons';

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

  return (
    <div
      style={{
        border: `2px solid ${borderColor}`,
        borderRadius: 8,
        padding: 12,
        background: token.colorBgContainer,
        minWidth: 200,
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
      {nodeData.retry_enabled && (
        <Tooltip title={`Retry: max ${nodeData.retry_max_attempts ?? 3} tentatives`}>
          <div style={{ fontSize: 11, color: token.colorPrimary, marginTop: 4 }}>
            <RetweetOutlined /> Retry activé
          </div>
        </Tooltip>
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
  );
};

export default memo(WorkflowStepNode);
