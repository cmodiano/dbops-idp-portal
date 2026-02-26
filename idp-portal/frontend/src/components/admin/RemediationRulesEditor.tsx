/**
 * RemediationRulesEditor component for managing action remediation rules visually (Story 9.1, Task 6).
 *
 * Features:
 * - List of remediation rules with "Ajouter une règle" button
 * - Inline form per rule: error_pattern (regex), target_action_id, environments, auto_trigger, risk_level
 * - Delete (X) per rule; inline validation: error_pattern required, target_action_id required
 * - Action dropdown populated from catalog
 * - Same pattern as ImpactRulesEditor
 *
 * Story 48.8 (SOLID-FE-4, AC4): fetchCatalogActions encapsulé dans useRemediationCatalogActions hook (DIP).
 */

import React from 'react';
import {
  Button,
  Input,
  Select,
  Space,
  Card,
  Typography,
  Form,
  Switch,
  Tag,
  Tooltip,
  Alert,
} from 'antd';
import { PlusOutlined, DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons';
import type { RemediationRule, RiskLevel } from '../../types/api';
import type { CatalogAction } from '../../services/catalog_service';
import { useRemediationCatalogActions } from '../../hooks/useRemediationCatalogActions';
import { useEnvironments } from '../../hooks/useEnvironments';

const { Text } = Typography;

/** Internal rule definition with ID for React keys. */
export interface RemediationRuleDefinition extends RemediationRule {
  id?: string;
}

export interface RemediationRulesEditorProps {
  value?: RemediationRuleDefinition[];
  onChange?: (value: RemediationRuleDefinition[]) => void;
  /** Current action ID (to exclude from target selection). */
  currentActionId?: number;
}

const EMPTY_REMEDIATION_RULES: RemediationRuleDefinition[] = [];

const RISK_LEVEL_OPTIONS: { value: RiskLevel; label: string }[] = [
  { value: 'low', label: 'Faible' },
  { value: 'medium', label: 'Moyen' },
  { value: 'high', label: 'Élevé' },
];

interface RuleCardProps {
  rule: RemediationRuleDefinition;
  index: number;
  actions: CatalogAction[];
  currentActionId?: number;
  environmentOptions: { value: string; label: string }[];
  environmentsLoading: boolean;
  onRuleChange: (index: number, field: keyof RemediationRuleDefinition, fieldValue: unknown) => void;
  onRemove: (index: number) => void;
}

const RuleCard: React.FC<RuleCardProps> = ({
  rule,
  index,
  actions,
  currentActionId,
  environmentOptions,
  environmentsLoading,
  onRuleChange,
  onRemove,
}) => {
  // Validate regex pattern
  const patternError = (() => {
    if (!rule.error_pattern?.trim()) return 'Pattern requis';
    try {
      new RegExp(rule.error_pattern);
      return '';
    } catch {
      return 'Pattern regex invalide';
    }
  })();

  // Filter out current action from dropdown
  const actionOptions = actions
    .filter((a) => a.id !== currentActionId)
    .map((a) => ({
      value: a.id,
      label: `${a.name} (${a.engine || 'N/A'})`,
    }));

  return (
    <Card
      size="small"
      styles={{ body: { padding: '12px' } }}
      style={{ marginBottom: 8 }}
    >
      <Space orientation="vertical" style={{ width: '100%' }} size="small">
        <Space align="center" style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Text strong>Règle {index + 1}</Text>
            <Tag color={rule.risk_level === 'high' ? 'red' : rule.risk_level === 'medium' ? 'orange' : 'green'}>
              {rule.risk_level}
            </Tag>
            {rule.auto_trigger && <Tag color="blue">Auto</Tag>}
          </Space>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onRemove(index)}
            aria-label={`Supprimer règle ${index + 1}`}
          />
        </Space>

        <Form.Item
          label={
            <Space>
              Pattern d'erreur (regex)
              <Tooltip title="Expression régulière à matcher contre le message d'erreur de l'exécution échouée. Ex: ORA-\\d+ ou timeout|connection refused">
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </Space>
          }
          validateStatus={patternError ? 'error' : ''}
          help={patternError}
          style={{ marginBottom: 8 }}
        >
          <Input
            value={rule.error_pattern}
            onChange={(e) => onRuleChange(index, 'error_pattern', e.target.value)}
            placeholder="Ex: ORA-\\d+|timeout"
            style={{ width: '100%' }}
            aria-label={`Pattern d'erreur règle ${index + 1}`}
          />
        </Form.Item>

        <Form.Item
          label="Action corrective cible"
          validateStatus={!rule.target_action_id ? 'error' : ''}
          help={!rule.target_action_id ? 'Action cible requise' : ''}
          style={{ marginBottom: 8 }}
        >
          <Select
            value={rule.target_action_id || undefined}
            onChange={(v) => onRuleChange(index, 'target_action_id', v)}
            options={actionOptions}
            placeholder="Sélectionnez une action"
            style={{ width: '100%' }}
            aria-label={`Action cible règle ${index + 1}`}
            showSearch
            filterOption={(input, option) =>
              (option?.label?.toString() || '').toLowerCase().includes(input.toLowerCase())
            }
          />
        </Form.Item>

        <Space wrap style={{ width: '100%' }} size="small">
          <Form.Item
            label="Environnements"
            validateStatus={!rule.environments || rule.environments.length === 0 ? 'error' : ''}
            help={!rule.environments || rule.environments.length === 0 ? 'Au moins un environnement requis' : ''}
            style={{ marginBottom: 8 }}
          >
            <Select
              mode="multiple"
              value={rule.environments}
              onChange={(v) => onRuleChange(index, 'environments', v)}
              options={environmentOptions}
              placeholder="Sélectionnez"
              style={{ width: 200 }}
              loading={environmentsLoading}
              disabled={environmentsLoading}
              aria-label={`Environnements règle ${index + 1}`}
            />
          </Form.Item>

          <Form.Item label="Niveau de risque" style={{ marginBottom: 8 }}>
            <Select
              value={rule.risk_level}
              onChange={(v) => onRuleChange(index, 'risk_level', v)}
              options={RISK_LEVEL_OPTIONS}
              style={{ width: 120 }}
              aria-label={`Niveau de risque règle ${index + 1}`}
            />
          </Form.Item>

          <Form.Item
            label={
              <Tooltip title={
                rule.risk_level !== 'low'
                  ? "Auto-déclenchement uniquement disponible pour risque 'Faible'"
                  : "Si activé, l'action corrective peut être déclenchée automatiquement sans validation utilisateur"
              }>
                <Space>
                  Déclenchement auto
                  <InfoCircleOutlined style={{ color: rule.risk_level !== 'low' ? '#faad14' : '#8c8c8c' }} />
                </Space>
              </Tooltip>
            }
            style={{ marginBottom: 8 }}
          >
            <Switch
              checked={rule.auto_trigger}
              onChange={(v) => onRuleChange(index, 'auto_trigger', v)}
              aria-label={`Déclenchement auto règle ${index + 1}`}
              disabled={rule.risk_level !== 'low'}
            />
          </Form.Item>
        </Space>

        {/* Story 9.3, AC4: Warning if auto + prod */}
        {/* Fix: Clarify that auto-trigger is BLOCKED in prod, not just requiring approval */}
        {rule.auto_trigger && rule.environments?.some(e => e.toLowerCase() === 'prod') && (
          <Alert
            type="error"
            showIcon
            title="Auto-déclenchement INTERDIT en Production"
            description="L'auto-déclenchement est bloqué en environnement Production. Cette règle sera refusée par l'API. Retirez 'prod' des environnements autorisés."
            style={{ marginTop: 8 }}
          />
        )}
      </Space>
    </Card>
  );
};

export const RemediationRulesEditor: React.FC<RemediationRulesEditorProps> = ({
  value = EMPTY_REMEDIATION_RULES,
  onChange,
  currentActionId,
}) => {
  const { catalogActions } = useRemediationCatalogActions();
  const { environments, environmentOptions, loading: environmentsLoading } = useEnvironments();

  const handleAdd = () => {
    const newRule: RemediationRuleDefinition = {
      id: `rule-new-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      error_pattern: '',
      target_action_id: 0,
      environments: [...environments],
      auto_trigger: false,
      risk_level: 'medium',
    };
    onChange?.([...value, newRule]);
  };

  const handleRemove = (index: number) => {
    onChange?.(value.filter((_, i) => i !== index));
  };

  const handleRuleChange = (index: number, field: keyof RemediationRuleDefinition, fieldValue: unknown) => {
    const next = [...value];
    const current = { ...next[index] };
    (current as Record<string, unknown>)[field] = fieldValue;

    // Story 9.3, AC4: Auto-disable auto_trigger if risk_level changes from 'low'
    if (field === 'risk_level' && fieldValue !== 'low' && current.auto_trigger) {
      current.auto_trigger = false;
    }

    next[index] = current;
    onChange?.(next);
  };

  return (
    <div>
      <Space orientation="vertical" style={{ width: '100%' }}>
        {value.map((rule, index) => (
          <RuleCard
            key={rule.id ?? `rule-${index}`}
            rule={rule}
            index={index}
            actions={catalogActions}
            currentActionId={currentActionId}
            environmentOptions={environmentOptions}
            environmentsLoading={environmentsLoading}
            onRuleChange={handleRuleChange}
            onRemove={handleRemove}
          />
        ))}

        {value.length === 0 && (
          <Text type="secondary">
            Aucune règle de remédiation. Configurez des règles pour proposer des actions correctives automatiques en cas d'échec.
          </Text>
        )}

        <Button type="dashed" onClick={handleAdd} icon={<PlusOutlined />} block>
          Ajouter une règle de remédiation
        </Button>
      </Space>
    </div>
  );
};

export default RemediationRulesEditor;
