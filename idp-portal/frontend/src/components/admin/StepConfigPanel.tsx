/**
 * StepConfigPanel — Drawer for configuring a selected workflow step (Story 16.5, AC5; Story 16.6).
 *
 * Shows action details, retry config with timeline preview, branch info (read-only).
 */

import React, { useMemo, useState, useEffect } from 'react';
import { Drawer, Input, Switch, InputNumber, Typography, Space, Button, Divider, Alert } from 'antd';
import { DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons';
import type { Node } from '@xyflow/react';
import type { WorkflowStepNodeData } from './WorkflowStepNode';
import { calculateRetryTimeline, formatDuration } from '../../utils/retryTimeline';

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

  const retryEnabled = Boolean(data.retry_enabled);
  const maxAttempts = data.retry_max_attempts ?? 3;
  const intervalSeconds = data.retry_interval_seconds ?? 60;
  const backoffMultiplier = data.retry_backoff_multiplier ?? 2.0;

  const retryTimeline = useMemo(
    () => retryEnabled ? calculateRetryTimeline(maxAttempts, intervalSeconds, backoffMultiplier) : [],
    [retryEnabled, maxAttempts, intervalSeconds, backoffMultiplier],
  );

  // Validation helpers
  const maxAttemptsError = retryEnabled && (maxAttempts < 1 || maxAttempts > 10);
  const intervalError = retryEnabled && intervalSeconds < 1;
  const backoffError = retryEnabled && (backoffMultiplier < 1.0 || backoffMultiplier > 10.0);

  const hasValidationErrors = maxAttemptsError || intervalError || backoffError;

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
      size="default"
      styles={{ body: { width: 360 } }}
      aria-label="Panneau de configuration de l'étape"
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
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

        {/* Retry config — Story 16.6 */}
        <div>
          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
            Options de retry
          </Text>
          <Space orientation="vertical" style={{ width: '100%' }} size="small">
            <Space align="center">
              <Text type="secondary" style={{ fontSize: 12 }}>Activer le retry automatique</Text>
              <Switch
                checked={retryEnabled}
                onChange={(checked) => handleFieldChange('retry_enabled', checked)}
                disabled={disabled}
                aria-label="Activer le retry automatique"
              />
            </Space>

            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                Nombre maximum de tentatives
              </Text>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                max={10}
                value={data.retry_max_attempts ?? null}
                onChange={(v) => handleFieldChange('retry_max_attempts', v ?? null)}
                disabled={disabled || !retryEnabled}
                aria-label="Nombre maximum de tentatives"
                status={maxAttemptsError ? 'error' : undefined}
              />
              {maxAttemptsError && (
                <Text type="danger" style={{ fontSize: 11, display: 'block' }} role="alert">
                  Doit être entre 1 et 10
                </Text>
              )}
            </div>

            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                Intervalle entre tentatives (secondes)
              </Text>
              <InputNumber
                style={{ width: '100%' }}
                min={1}
                value={data.retry_interval_seconds ?? null}
                onChange={(v) => handleFieldChange('retry_interval_seconds', v ?? null)}
                disabled={disabled || !retryEnabled}
                aria-label="Intervalle entre tentatives"
                status={intervalError ? 'error' : undefined}
              />
              {intervalError && (
                <Text type="danger" style={{ fontSize: 11, display: 'block' }} role="alert">
                  Doit être au moins 1 seconde
                </Text>
              )}
            </div>

            <div>
              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                Multiplicateur de backoff
              </Text>
              <InputNumber
                style={{ width: '100%' }}
                min={1.0}
                max={10.0}
                step={0.1}
                value={data.retry_backoff_multiplier ?? null}
                onChange={(v) => handleFieldChange('retry_backoff_multiplier', v ?? null)}
                disabled={disabled || !retryEnabled}
                aria-label="Multiplicateur de backoff"
                status={backoffError ? 'error' : undefined}
              />
              {backoffError && (
                <Text type="danger" style={{ fontSize: 11, display: 'block' }} role="alert">
                  Doit être entre 1.0 et 10.0
                </Text>
              )}
            </div>

            <Alert
              type="info"
              showIcon
              icon={<InfoCircleOutlined />}
              title="L'intervalle sera multiplié par ce facteur à chaque tentative (backoff exponentiel)"
              style={{ marginTop: 4 }}
            />

            {/* Timeline preview — Story 16.6, AC4 */}
            {retryEnabled && retryTimeline.length > 0 && (
              <div data-testid="retry-timeline-preview" style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                  Prévisualisation de la timeline
                </Text>
                <ul style={{ paddingLeft: 20, margin: 0, fontSize: 12 }}>
                  {retryTimeline.map(({ attempt, delay }) => (
                    <li key={attempt}>
                      Tentative {attempt} : {delay === 0 ? 'immédiate' : `${formatDuration(delay)}`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
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

        {/* Validation warning */}
        {hasValidationErrors && (
          <Alert
            type="warning"
            showIcon
            title="Valeurs de retry invalides"
            description="Corrigez les erreurs ci-dessus avant de sauvegarder le workflow."
            style={{ marginBottom: 8 }}
          />
        )}

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
