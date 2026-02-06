/**
 * StepConfigPanel — Drawer for configuring a selected workflow step (Story 16.5, AC5).
 *
 * Shows action details, retry config, branch info (read-only — branches are managed via canvas connections).
 */

import React from 'react';
import { Drawer, Input, Switch, InputNumber, Typography, Space, Button, Divider } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import type { Node } from '@xyflow/react';
import type { WorkflowStepNodeData } from './WorkflowStepNode';

const { Text, Title } = Typography;

export interface StepConfigPanelProps {
  node: Node | null;
  open: boolean;
  onClose: () => void;
  onNodeUpdate: (nodeId: string, data: Partial<WorkflowStepNodeData>) => void;
  onNodeDelete: (nodeId: string) => void;
  disabled?: boolean;
}

export const StepConfigPanel: React.FC<StepConfigPanelProps> = ({
  node,
  open,
  onClose,
  onNodeUpdate,
  onNodeDelete,
  disabled = false,
}) => {
  if (!node) return null;

  const data = node.data as unknown as WorkflowStepNodeData;

  const handleFieldChange = (field: keyof WorkflowStepNodeData, value: unknown) => {
    if (disabled) return;
    const updates: Partial<WorkflowStepNodeData> = { [field]: value };

    // Apply defaults when enabling retry
    if (field === 'retry_enabled' && value === true) {
      if (data.retry_max_attempts == null) updates.retry_max_attempts = 3;
      if (data.retry_interval_seconds == null) updates.retry_interval_seconds = 60;
      if (data.retry_backoff_multiplier == null) updates.retry_backoff_multiplier = 2.0;
    }

    onNodeUpdate(node.id, updates);
  };

  return (
    <Drawer
      title="Configuration de l'étape"
      open={open}
      onClose={onClose}
      width={360}
      aria-label="Panneau de configuration de l'étape"
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* Action details */}
        <div>
          <Title level={5} style={{ margin: 0 }}>
            {data.action_name}
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {data.action_engine}
            {data.action_platform ? ` / ${data.action_platform}` : ''}
          </Text>
        </div>

        <Divider style={{ margin: '8px 0' }} />

        {/* Display name */}
        <div>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            Nom d'affichage
          </Text>
          <Input
            value={data.name ?? ''}
            onChange={(e) => handleFieldChange('name', e.target.value || null)}
            placeholder="Optionnel"
            aria-label="Nom d'affichage de l'étape"
            disabled={disabled}
          />
        </div>

        {/* Step ID */}
        <div>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
            ID d'étape (step_id)
          </Text>
          <Input value={node.id} disabled aria-label="step_id" />
        </div>

        <Divider style={{ margin: '8px 0' }} />

        {/* Retry config */}
        <div>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            Retry
          </Text>
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Space align="center">
              <Text type="secondary" style={{ fontSize: 12 }}>Activé</Text>
              <Switch
                checked={Boolean(data.retry_enabled)}
                onChange={(checked) => handleFieldChange('retry_enabled', checked)}
                disabled={disabled}
                aria-label="Retry activé"
              />
            </Space>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                Max tentatives
              </Text>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                value={data.retry_max_attempts ?? null}
                onChange={(v) => handleFieldChange('retry_max_attempts', v ?? null)}
                disabled={disabled || !data.retry_enabled}
                aria-label="Max tentatives"
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                Intervalle (secondes)
              </Text>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                value={data.retry_interval_seconds ?? null}
                onChange={(v) => handleFieldChange('retry_interval_seconds', v ?? null)}
                disabled={disabled || !data.retry_enabled}
                aria-label="Intervalle retry"
              />
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                Multiplicateur backoff
              </Text>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                step={0.1}
                value={data.retry_backoff_multiplier ?? null}
                onChange={(v) => handleFieldChange('retry_backoff_multiplier', v ?? null)}
                disabled={disabled || !data.retry_enabled}
                aria-label="Backoff multiplier"
              />
            </div>
          </Space>
        </div>

        <Divider style={{ margin: '8px 0' }} />

        {/* Branch info (read-only) */}
        <div>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            Branchements
          </Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Les connexions de branchement (succès/erreur) se gèrent directement sur le canvas en reliant les ports des nœuds.
          </Text>
        </div>

        <Divider style={{ margin: '8px 0' }} />

        {/* Delete button */}
        <Button
          danger
          icon={<DeleteOutlined />}
          onClick={() => {
            onNodeDelete(node.id);
            onClose();
          }}
          disabled={disabled}
          block
        >
          Supprimer cette étape
        </Button>
      </Space>
    </Drawer>
  );
};

export default StepConfigPanel;
